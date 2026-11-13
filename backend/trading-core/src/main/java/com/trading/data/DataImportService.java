package com.trading.data;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.*;
import java.time.format.DateTimeParseException;
import java.util.*;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

@Service
public class DataImportService {
  private static final Set<String> EXCHANGES = Set.of("NSE", "BSE");
  private static final Set<String> LISTING_STATUSES = Set.of("ACTIVE", "INACTIVE", "DELISTED");
  private static final Set<String> ACTIONS = Set.of("SPLIT", "BONUS", "DIVIDEND", "RIGHTS", "MERGER", "DEMERGER", "SYMBOL_CHANGE");
  private static final ZoneId INDIA = ZoneId.of("Asia/Kolkata");
  private final JdbcTemplate jdbc;
  private final TransactionTemplate transactions;
  private final ObjectMapper json;

  public DataImportService(JdbcTemplate jdbc, TransactionTemplate transactions, ObjectMapper json) {
    this.jdbc = jdbc; this.transactions = transactions; this.json = json;
  }

  public Map<String,Object> importCsv(String type, String filename, byte[] bytes) {
    String job = switch (type) {
      case "instruments", "market-sessions", "corporate-actions", "daily-candles" -> type;
      default -> throw new ImportRejectedException("Unsupported import type: " + type);
    };
    long sourceId = jdbc.queryForObject("SELECT id FROM data_sources WHERE source_code='MANUAL_CSV' AND enabled", Long.class);
    String hash = sha256(bytes);
    List<Map<String,Object>> prior = jdbc.queryForList("SELECT id,records_seen,records_written FROM ingestion_runs WHERE source_id=? AND job_name=? AND artifact_sha256=? AND status='SUCCESS'", sourceId, job, hash);
    if (!prior.isEmpty()) {
      UUID original=(UUID)prior.get(0).get("id"); long seen=number(prior.get(0).get("records_seen"));
      UUID duplicate=jdbc.queryForObject("""
        INSERT INTO ingestion_runs(source_id,job_name,started_at,finished_at,status,artifact_name,artifact_sha256,records_seen,records_written,cursor_value,quality_summary)
        VALUES (?, ?, now(), now(), 'DUPLICATE', ?, ?, ?, 0, ?, '{"duplicate":true}'::jsonb) RETURNING id
        """,UUID.class,sourceId,job,safeFilename(filename),hash,seen,original.toString());
      return response(duplicate, "DUPLICATE", seen, 0, "Identical successful artifact already imported; original run " + original);
    }
    UUID runId = jdbc.queryForObject("""
      INSERT INTO ingestion_runs(source_id,job_name,started_at,status,artifact_name,artifact_sha256)
      VALUES (?, ?, now(), 'RUNNING', ?, ?) RETURNING id
      """, UUID.class, sourceId, job, safeFilename(filename), hash);
    try {
      ImportResult result = transactions.execute(status -> switch (job) {
        case "instruments" -> importInstruments(runId, sourceId, bytes);
        case "market-sessions" -> importSessions(runId, sourceId, bytes);
        case "corporate-actions" -> importActions(runId, sourceId, bytes);
        default -> importCandles(runId, sourceId, bytes);
      });
      jdbc.update("UPDATE ingestion_runs SET finished_at=now(),status='SUCCESS',records_seen=?,records_written=?,failure_count=0,source_revision=?,quality_summary=?::jsonb WHERE id=?",
        result.seen, result.written, result.sourceRevision, toJson(Map.of("qualityEvents", result.qualityEvents)), runId);
      return response(runId, "SUCCESS", result.seen, result.written, result.qualityEvents + " quality event(s) recorded");
    } catch (Exception raw) {
      String message = rootMessage(raw);
      jdbc.update("UPDATE ingestion_runs SET finished_at=now(),status='FAILED',failure_count=1,error_message=? WHERE id=?", message, runId);
      quality(sourceId, null, runId, "ERROR", "FILE_REJECTED", null, Map.of("message", message, "artifact", safeFilename(filename)));
      if (raw instanceof ImportRejectedException rejected) throw rejected;
      throw new ImportRejectedException(message, raw);
    }
  }

  private ImportResult importInstruments(UUID run, long source, byte[] bytes) {
    String header=new String(bytes,StandardCharsets.UTF_8).replace("\uFEFF","").lines().findFirst().orElse("");
    boolean named=header.contains("security_name");
    List<Map<String,String>> rows = CsvTable.parse(bytes, named
      ? List.of("exchange","symbol","series","isin","security_name","instrument_type","exchange_token","listing_status","listed_on","delisted_on","source_revision")
      : List.of("exchange","symbol","series","isin","instrument_type","exchange_token","listing_status","listed_on","delisted_on","source_revision"));
    Set<String> keys = new HashSet<>(); int written = 0; String revision = null;
    for (Map<String,String> row : rows) {
      int line = line(row); String exchange = exchange(row, line); String symbol = symbol(row, line); String series = optional(row, "series");
      String key = exchange + "|" + symbol + "|" + Objects.toString(series, "");
      if (!keys.add(key)) reject(line, "duplicate instrument key in file");
      String isin = optional(row, "isin"); if (isin != null && (!isin.matches("[A-Z]{2}[A-Z0-9]{9}[0-9]") || !validIsin(isin))) reject(line, "invalid ISIN or checksum");
      String securityName=optional(row,"security_name"); if(securityName!=null&&securityName.length()>250)reject(line,"security_name exceeds 250 characters");
      String type = required(row, "instrument_type", line).toUpperCase(Locale.ROOT); if (!type.matches("[A-Z_]{2,20}")) reject(line, "invalid instrument_type");
      String token = optional(row, "exchange_token"); String listing = required(row,"listing_status",line).toUpperCase(Locale.ROOT);
      if (!LISTING_STATUSES.contains(listing)) reject(line, "listing_status must be ACTIVE, INACTIVE or DELISTED");
      LocalDate listed = date(optional(row,"listed_on"), line, "listed_on"); LocalDate delisted = date(optional(row,"delisted_on"), line, "delisted_on");
      if (listing.equals("DELISTED") && delisted == null) reject(line, "DELISTED instruments require delisted_on");
      if (listed != null && delisted != null && delisted.isBefore(listed)) reject(line, "delisted_on precedes listed_on");
      revision = required(row,"source_revision",line); if (revision.length() > 120) reject(line, "source_revision exceeds 120 characters");
      written += jdbc.update("""
        INSERT INTO instruments(exchange_id,symbol,series,isin,security_name,instrument_type,exchange_token,active,source,source_id,listing_status,listed_on,delisted_on,source_revision,updated_at)
        VALUES ((SELECT id FROM exchanges WHERE code=?),?,?,?,?,?,?,?, 'MANUAL_CSV',?,?,?,?,?,now())
        ON CONFLICT (exchange_id,symbol,COALESCE(series,'')) DO UPDATE SET isin=EXCLUDED.isin,security_name=COALESCE(EXCLUDED.security_name,instruments.security_name),instrument_type=EXCLUDED.instrument_type,
        exchange_token=EXCLUDED.exchange_token,active=EXCLUDED.active,source_id=EXCLUDED.source_id,listing_status=EXCLUDED.listing_status,
        listed_on=EXCLUDED.listed_on,delisted_on=EXCLUDED.delisted_on,source_revision=EXCLUDED.source_revision,updated_at=now()
        """, exchange,symbol,series,isin,securityName,type,token,listing.equals("ACTIVE"),source,listing,listed,delisted,revision);
    }
    return new ImportResult(rows.size(), written, 0, revision);
  }

  private ImportResult importSessions(UUID run, long source, byte[] bytes) {
    List<Map<String,String>> rows = CsvTable.parse(bytes, List.of("exchange","session_date","session_type","is_trading_day","open_time","close_time","source_revision"));
    Set<String> keys = new HashSet<>(); int written = 0; String revision = null;
    for (Map<String,String> row : rows) {
      int line=line(row); String exchange=exchange(row,line); LocalDate day=requiredDate(row,"session_date",line);
      String type=required(row,"session_type",line).toUpperCase(Locale.ROOT); if (!type.matches("[A-Z_]{2,30}")) reject(line,"invalid session_type");
      if (!keys.add(exchange+"|"+day+"|"+type)) reject(line,"duplicate session in file");
      String tradingText=required(row,"is_trading_day",line).toLowerCase(Locale.ROOT); if (!Set.of("true","false").contains(tradingText)) reject(line,"is_trading_day must be true or false");
      boolean trading=Boolean.parseBoolean(tradingText); OffsetDateTime open=timestamp(optional(row,"open_time"),line,"open_time"); OffsetDateTime close=timestamp(optional(row,"close_time"),line,"close_time");
      if (trading && (open==null || close==null)) reject(line,"trading days require open_time and close_time");
      if (open!=null && close!=null && !close.isAfter(open)) reject(line,"close_time must be after open_time");
      if (open!=null && !open.atZoneSameInstant(INDIA).toLocalDate().equals(day)) reject(line,"open_time is outside session_date in Asia/Kolkata");
      if (close!=null && !close.atZoneSameInstant(INDIA).toLocalDate().equals(day)) reject(line,"close_time is outside session_date in Asia/Kolkata");
      revision=required(row,"source_revision",line);
      written += jdbc.update("""
        INSERT INTO market_sessions(exchange_id,session_date,session_type,open_time,close_time,is_trading_day,source_id,ingestion_run_id,source_revision,received_at)
        VALUES ((SELECT id FROM exchanges WHERE code=?),?,?,?,?,?,?,?, ?,now())
        ON CONFLICT(exchange_id,session_date,session_type) DO UPDATE SET open_time=EXCLUDED.open_time,close_time=EXCLUDED.close_time,
        is_trading_day=EXCLUDED.is_trading_day,source_id=EXCLUDED.source_id,ingestion_run_id=EXCLUDED.ingestion_run_id,source_revision=EXCLUDED.source_revision,received_at=now()
        """,exchange,day,type,open,close,trading,source,run,revision);
    }
    return new ImportResult(rows.size(),written,0,revision);
  }

  private ImportResult importActions(UUID run, long source, byte[] bytes) {
    List<Map<String,String>> rows=CsvTable.parse(bytes,List.of("exchange","symbol","series","action_type","ex_date","ratio","cash_amount","source_revision"));
    Set<String> keys=new HashSet<>(); int written=0; String revision=null;
    for(Map<String,String> row:rows){
      int line=line(row); long instrument=instrument(exchange(row,line),symbol(row,line),optional(row,"series"),line);
      String action=required(row,"action_type",line).toUpperCase(Locale.ROOT); if(!ACTIONS.contains(action)) reject(line,"unsupported action_type");
      LocalDate exDate=requiredDate(row,"ex_date",line); BigDecimal ratio=decimal(optional(row,"ratio"),line,"ratio"); BigDecimal cash=decimal(optional(row,"cash_amount"),line,"cash_amount");
      if((ratio!=null&&ratio.signum()<0)||(cash!=null&&cash.signum()<0)) reject(line,"ratio and cash_amount cannot be negative");
      if(Set.of("SPLIT","BONUS","RIGHTS").contains(action)&&(ratio==null||ratio.signum()<=0)) reject(line,action+" requires a positive ratio");
      revision=required(row,"source_revision",line); String key=instrument+"|"+action+"|"+exDate+"|"+revision; if(!keys.add(key)) reject(line,"duplicate corporate action in file");
      written += jdbc.update("""
        INSERT INTO corporate_actions(instrument_id,issuer_id,action_type,ex_date,ratio,cash_amount,source_id,source_revision,raw_payload,ingestion_run_id,received_at)
        SELECT id,issuer_id,?,?,?,?,?,?, '{}'::jsonb,?,now() FROM instruments WHERE id=?
        ON CONFLICT (instrument_id,action_type,ex_date,COALESCE(source_revision,'')) DO UPDATE SET ratio=EXCLUDED.ratio,cash_amount=EXCLUDED.cash_amount,
        source_id=EXCLUDED.source_id,ingestion_run_id=EXCLUDED.ingestion_run_id,received_at=now()
        """,action,exDate,ratio,cash,source,revision,run,instrument);
    }
    return new ImportResult(rows.size(),written,0,revision);
  }

  private ImportResult importCandles(UUID run,long source,byte[] bytes){
    List<Map<String,String>> rows=CsvTable.parse(bytes,List.of("exchange","symbol","series","trade_date","open","high","low","close","volume","adjustment_status","source_revision"));
    Set<String> keys=new HashSet<>(); int written=0, events=0; String revision=null; LocalDate newest=null;
    for(Map<String,String> row:rows){
      int line=line(row); String exchange=exchange(row,line); long instrument=instrument(exchange,symbol(row,line),optional(row,"series"),line); LocalDate day=requiredDate(row,"trade_date",line);
      if(day.isAfter(LocalDate.now(INDIA))) reject(line,"trade_date is in the future");
      List<Map<String,Object>> session=jdbc.queryForList("""
        SELECT close_time FROM market_sessions ms JOIN exchanges e ON e.id=ms.exchange_id
        WHERE e.code=? AND session_date=? AND is_trading_day AND session_type='REGULAR' AND close_time IS NOT NULL
        """,exchange,day);
      if(session.size()!=1) reject(line,"no single validated REGULAR trading session maps this candle date");
      OffsetDateTime candleTime=((java.sql.Timestamp)session.get(0).get("close_time")).toInstant().atOffset(ZoneOffset.UTC);
      String key=instrument+"|"+day; if(!keys.add(key)) reject(line,"duplicate instrument/date candle in file");
      BigDecimal open=positive(row,"open",line),high=positive(row,"high",line),low=positive(row,"low",line),close=positive(row,"close",line);
      if(high.compareTo(open)<0||high.compareTo(close)<0||high.compareTo(low)<0||low.compareTo(open)>0||low.compareTo(close)>0) reject(line,"OHLC consistency failed");
      long volume=whole(row,"volume",line); if(volume<0) reject(line,"volume cannot be negative");
      String adjustment=required(row,"adjustment_status",line).toUpperCase(Locale.ROOT); if(!Set.of("RAW_UNADJUSTED","ADJUSTED").contains(adjustment)) reject(line,"adjustment_status must be RAW_UNADJUSTED or ADJUSTED");
      revision=required(row,"source_revision",line);
      List<Map<String,Object>> existing=jdbc.queryForList("SELECT open,high,low,close,volume,adjustment_status FROM market_candles WHERE instrument_id=? AND timeframe='1d' AND candle_time=?",instrument,candleTime);
      boolean changed=!existing.isEmpty()&&!sameCandle(existing.get(0),open,high,low,close,volume,adjustment);
      written += jdbc.update("""
        INSERT INTO market_candles(instrument_id,timeframe,candle_time,source_id,open,high,low,close,volume,is_complete,quality_status,revision,ingestion_run_id,received_at,source_revision,adjustment_status)
        VALUES (?,'1d',?,?,?,?,?,?,?,?, 'VALIDATED_MANUAL',1,?,now(),?,?)
        ON CONFLICT(instrument_id,timeframe,candle_time) DO UPDATE SET source_id=EXCLUDED.source_id,open=EXCLUDED.open,high=EXCLUDED.high,
        low=EXCLUDED.low,close=EXCLUDED.close,volume=EXCLUDED.volume,is_complete=TRUE,quality_status='VALIDATED_MANUAL',revision=market_candles.revision+1,
        ingestion_run_id=EXCLUDED.ingestion_run_id,received_at=now(),source_revision=EXCLUDED.source_revision,adjustment_status=EXCLUDED.adjustment_status
        WHERE (market_candles.open,market_candles.high,market_candles.low,market_candles.close,market_candles.volume,market_candles.adjustment_status)
          IS DISTINCT FROM (EXCLUDED.open,EXCLUDED.high,EXCLUDED.low,EXCLUDED.close,EXCLUDED.volume,EXCLUDED.adjustment_status)
        """,instrument,candleTime,source,open,high,low,close,volume,true,run,revision,adjustment);
      if(changed){ quality(source,instrument,run,"INFO","CANDLE_REVISION",candleTime.toInstant(),Map.of("tradeDate",day.toString(),"sourceRevision",revision)); events++; }
      List<BigDecimal> prior=jdbc.query("SELECT close FROM market_candles WHERE instrument_id=? AND timeframe='1d' AND candle_time<? ORDER BY candle_time DESC LIMIT 1",(rs,n)->rs.getBigDecimal(1),instrument,candleTime);
      if(!prior.isEmpty()&&prior.get(0).signum()>0){
        BigDecimal move=close.subtract(prior.get(0)).abs().divide(prior.get(0),6,java.math.RoundingMode.HALF_UP);
        if(move.compareTo(new BigDecimal("0.25"))>0){
          boolean action=Boolean.TRUE.equals(jdbc.queryForObject("SELECT EXISTS(SELECT 1 FROM corporate_actions WHERE instrument_id=? AND ex_date=?)",Boolean.class,instrument,day));
          quality(source,instrument,run,action?"INFO":"WARNING",action?"CORPORATE_ACTION_CONTEXT":"SUSPICIOUS_PRICE_DISCONTINUITY",candleTime.toInstant(),Map.of("absoluteReturn",move,"tradeDate",day.toString(),"adjustmentStatus",adjustment)); events++;
        }
      }
      newest=newest==null||day.isAfter(newest)?day:newest;
    }
    if(newest!=null&&newest.isBefore(LocalDate.now(INDIA).minusDays(10))){ quality(source,null,run,"WARNING","STALE_SOURCE",null,Map.of("latestTradeDate",newest.toString(),"ageDays",Duration.between(newest.atStartOfDay(INDIA),ZonedDateTime.now(INDIA)).toDays())); events++; }
    return new ImportResult(rows.size(),written,events,revision);
  }

  private long instrument(String exchange,String symbol,String series,int line){
    List<Long> ids=jdbc.query("SELECT i.id FROM instruments i JOIN exchanges e ON e.id=i.exchange_id WHERE e.code=? AND i.symbol=? AND COALESCE(i.series,'')=COALESCE(?,'')",(rs,n)->rs.getLong(1),exchange,symbol,series);
    if(ids.size()!=1) reject(line,"instrument mapping not found or ambiguous for "+exchange+":"+symbol+":"+Objects.toString(series,"")); return ids.get(0);
  }
  private void quality(long source,Long instrument,UUID run,String severity,String type,Instant eventTime,Map<String,Object> details){ jdbc.update("INSERT INTO data_quality_events(source_id,instrument_id,ingestion_run_id,severity,event_type,event_time,details) VALUES (?,?,?,?,?,?,?::jsonb)",source,instrument,run,severity,type,eventTime==null?null:OffsetDateTime.ofInstant(eventTime,ZoneOffset.UTC),toJson(details)); }
  private String exchange(Map<String,String> r,int l){String v=required(r,"exchange",l).toUpperCase(Locale.ROOT);if(!EXCHANGES.contains(v))reject(l,"exchange must be NSE or BSE");return v;}
  private String symbol(Map<String,String> r,int l){String v=required(r,"symbol",l).toUpperCase(Locale.ROOT);if(!v.matches("[A-Z0-9._&-]{1,50}"))reject(l,"invalid symbol");return v;}
  private static String required(Map<String,String> r,String k,int l){String v=r.get(k);if(v==null||v.isBlank())reject(l,k+" is required");return v.trim();}
  private static String optional(Map<String,String> r,String k){String v=r.get(k);return v==null||v.isBlank()?null:v.trim();}
  private static int line(Map<String,String> r){return Integer.parseInt(r.get("_line"));}
  private static LocalDate requiredDate(Map<String,String> r,String k,int l){LocalDate d=date(optional(r,k),l,k);if(d==null)reject(l,k+" is required");return d;}
  private static LocalDate date(String v,int l,String field){if(v==null)return null;try{return LocalDate.parse(v);}catch(DateTimeParseException e){reject(l,field+" must use YYYY-MM-DD");return null;}}
  private static OffsetDateTime timestamp(String v,int l,String field){if(v==null)return null;try{return OffsetDateTime.parse(v);}catch(DateTimeParseException e){reject(l,field+" must be ISO-8601 with an offset");return null;}}
  private static BigDecimal decimal(String v,int l,String field){if(v==null)return null;try{return new BigDecimal(v);}catch(NumberFormatException e){reject(l,field+" is not a valid decimal");return null;}}
  private static BigDecimal positive(Map<String,String> r,String k,int l){BigDecimal v=decimal(required(r,k,l),l,k);if(v.signum()<=0)reject(l,k+" must be positive");return v;}
  private static long whole(Map<String,String> r,String k,int l){try{return Long.parseLong(required(r,k,l));}catch(NumberFormatException e){reject(l,k+" must be a whole number");return 0;}}
  private static void reject(int line,String message){throw new ImportRejectedException("Line "+line+": "+message);}
  private static boolean validIsin(String isin){int sum=0;boolean twice=false;StringBuilder digits=new StringBuilder();for(char c:isin.toCharArray())digits.append(Character.isDigit(c)?String.valueOf(c):Integer.toString(c-'A'+10));for(int i=digits.length()-1;i>=0;i--){int n=digits.charAt(i)-'0';if(twice)n*=2;sum+=n/10+n%10;twice=!twice;}return sum%10==0;}
  private static boolean sameCandle(Map<String,Object> e,BigDecimal o,BigDecimal h,BigDecimal l,BigDecimal c,long v,String a){return ((BigDecimal)e.get("open")).compareTo(o)==0&&((BigDecimal)e.get("high")).compareTo(h)==0&&((BigDecimal)e.get("low")).compareTo(l)==0&&((BigDecimal)e.get("close")).compareTo(c)==0&&number(e.get("volume"))==v&&Objects.equals(e.get("adjustment_status"),a);}
  private static long number(Object value){return value==null?0:((Number)value).longValue();}
  private static String safeFilename(String name){String v=name==null?"upload.csv":name.replaceAll("[^A-Za-z0-9._-]","_");return v.substring(0,Math.min(v.length(),255));}
  private static String sha256(byte[] bytes){try{return java.util.HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));}catch(Exception e){throw new IllegalStateException(e);}}
  private String toJson(Object value){try{return json.writeValueAsString(value);}catch(JsonProcessingException e){throw new IllegalStateException(e);}}
  private static String rootMessage(Throwable e){Throwable root=e;while(root.getCause()!=null)root=root.getCause();String message=root.getMessage();return (message==null?root.getClass().getSimpleName():message).substring(0,Math.min(message==null?root.getClass().getSimpleName().length():message.length(),2000));}
  private static Map<String,Object> response(UUID id,String status,long seen,long written,String message){Map<String,Object> out=new LinkedHashMap<>();out.put("runId",id);out.put("status",status);out.put("recordsSeen",seen);out.put("recordsWritten",written);out.put("message",message);return out;}
  private record ImportResult(int seen,int written,int qualityEvents,String sourceRevision){}
}
