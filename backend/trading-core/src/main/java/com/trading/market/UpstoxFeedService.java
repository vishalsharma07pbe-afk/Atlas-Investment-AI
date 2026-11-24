package com.trading.market;
import com.fasterxml.jackson.databind.*;
import com.trading.api.*;
import java.math.*;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.*;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
@Service public class UpstoxFeedService {
 private final JdbcTemplate jdbc;private final FeedHttp http;private final VersionedVaultReader vault;
 private final ObjectMapper json=new ObjectMapper();
 public UpstoxFeedService(JdbcTemplate jdbc,FeedHttp http,VersionedVaultReader vault){this.jdbc=jdbc;this.http=http;this.vault=vault;}
 private static final String MASTER="https://assets.upstox.com/market-quote/instruments/exchange/";
 public int syncMaster()throws Exception{
  int count=0;
  for(String exchange:List.of("NSE","BSE")){
   // NSE's valid decompressed BOD JSON is currently larger than 40 MB. Keep a
   // strict ceiling, then retain only cash-equity identifiers used by holdings.
   JsonNode root=json.readTree(http.get(MASTER+exchange+".json.gz",null,60_000_000));
   if(!root.isArray())throw new IllegalStateException("Invalid instrument master");
   for(JsonNode item:root){
    String key=item.path("instrument_key").asText(""),symbol=item.path("trading_symbol").asText("");
    if(key.isBlank()||symbol.isBlank()||!key.startsWith(exchange+"_EQ|"))continue;
    String displayName=item.path("name").asText(item.path("short_name").asText(""));
    if(displayName.isBlank())displayName=null;
    else if(displayName.length()>240)displayName=displayName.substring(0,240);
    String isin=item.path("isin").asText(null);
    if(isin!=null&&!isin.matches("[A-Z]{2}[A-Z0-9]{9}[0-9]"))isin=null;
    jdbc.update("INSERT INTO upstox_instrument_map(instrument_key,exchange_code,isin,trading_symbol,instrument_type,display_name) VALUES (?,?,?,?,?,?) ON CONFLICT(instrument_key) DO UPDATE SET exchange_code=EXCLUDED.exchange_code,isin=EXCLUDED.isin,trading_symbol=EXCLUDED.trading_symbol,instrument_type=EXCLUDED.instrument_type,display_name=EXCLUDED.display_name,updated_at=now()",key,exchange,isin,symbol,item.path("instrument_type").asText(null),displayName);
    // Keep the canonical registry in sync with the documented provider master.
    // This makes search results immediately usable by historical ingestion and
    // research instead of requiring a separate manual registry import.
    jdbc.update("""
      INSERT INTO instruments(exchange_id,symbol,series,isin,security_name,instrument_type,
        listing_status,active,source,source_revision,updated_at)
      VALUES ((SELECT id FROM exchanges WHERE code=?),?,'EQ',?,?,?,'ACTIVE',true,
        'UPSTOX','UPSTOX_INSTRUMENT_MASTER',now())
      ON CONFLICT(exchange_id,symbol,series) DO UPDATE SET
        isin=COALESCE(EXCLUDED.isin,instruments.isin),
        security_name=COALESCE(EXCLUDED.security_name,instruments.security_name),
        instrument_type=EXCLUDED.instrument_type,listing_status='ACTIVE',active=true,
        source='UPSTOX',source_revision='UPSTOX_INSTRUMENT_MASTER',updated_at=now()
      """,exchange,symbol,isin,displayName,item.path("instrument_type").asText("EQUITY"));
    count++;
   }
  }
  return count;
 }
 public List<Map<String,Object>> search(String q){
  String term=q.trim();if(term.length()<1||term.length()>100)throw new IllegalArgumentException("Search must be 1..100 characters");
  return jdbc.queryForList("""
    WITH matches AS (
      SELECT instrument_key,exchange_code,isin,trading_symbol,instrument_type,display_name,updated_at,
        row_number() OVER (PARTITION BY lower(trading_symbol) ORDER BY
          CASE WHEN exchange_code='NSE' THEN 0 ELSE 1 END,instrument_key) exchange_preference
      FROM upstox_instrument_map
      WHERE trading_symbol ILIKE ? OR isin ILIKE ? OR display_name ILIKE ?
    )
    SELECT instrument_key,exchange_code,isin,trading_symbol,instrument_type,display_name,updated_at
    FROM matches WHERE exchange_preference=1
    ORDER BY CASE
      WHEN lower(trading_symbol)=lower(?) THEN 0
      WHEN lower(trading_symbol) LIKE lower(?) THEN 1
      WHEN lower(display_name) LIKE lower(?) THEN 2
      ELSE 3 END,
      CASE WHEN exchange_code='NSE' THEN 0 ELSE 1 END,
      length(trading_symbol),trading_symbol
    LIMIT 20
    ""","%"+term+"%","%"+term+"%","%"+term+"%",term,term+"%",term+"%");
 }
 private String token(UUID user){String t=vault.decrypt(user,"UPSTOX");if(t==null||t.isBlank())throw new IllegalStateException("Upstox credential unavailable");return t;}
 public JsonNode quote(UUID user,String key)throws Exception{
  if(jdbc.queryForObject("SELECT count(*) FROM upstox_instrument_map WHERE instrument_key=?",Integer.class,key)==0)throw new IllegalArgumentException("Unknown instrument");
  String url="https://api.upstox.com/v2/market-quote/quotes?instrument_key="+URLEncoder.encode(key,StandardCharsets.UTF_8);
  JsonNode body=json.readTree(http.text(url,token(user),2_000_000));
  if(!"success".equals(body.path("status").asText()))throw new IllegalStateException("Provider rejected quote");
  JsonNode data=body.path("data");if(!data.isObject()||data.isEmpty())throw new IllegalStateException("Empty quote");
  JsonNode quote=data.elements().next();BigDecimal ltp=quote.path("last_price").decimalValue();
  if(ltp.signum()<0)throw new IllegalStateException("Invalid price");
  BigDecimal previousClose=quote.path("ohlc").path("close").isNumber()
    ?quote.path("ohlc").path("close").decimalValue():null;
  if(previousClose!=null&&previousClose.signum()<0)previousClose=null;
  Instant timestamp=Instant.now();
  jdbc.update("INSERT INTO upstox_market_quotes(instrument_key,ltp,source_code,quoted_at) VALUES (?,?,'UPSTOX',?) ON CONFLICT(instrument_key) DO UPDATE SET ltp=EXCLUDED.ltp,quoted_at=EXCLUDED.quoted_at,received_at=now()",key,ltp,java.sql.Timestamp.from(timestamp));
  var result=json.createObjectNode().put("instrument_key",key).put("ltp",ltp).put("as_of",timestamp.toString()).put("source","UPSTOX");
  if(previousClose!=null)result.put("previous_close",previousClose);
  return result;
 }
 public int intradayCandles(UUID user,String key,String timeframe,LocalDate from,LocalDate to)throws Exception{
  if(!Set.of("1minute","15minute").contains(timeframe))throw new IllegalArgumentException("Unsupported timeframe");
  if(from.isAfter(to)||from.isBefore(LocalDate.now().minusDays(30)))throw new IllegalArgumentException("Invalid intraday range");
  return ingestCandles(token(user),key,from,to,timeframe);
 }
 public int dailyCandles(UUID user,String key,LocalDate from,LocalDate to)throws Exception{
  return ingestCandles(token(user),key,from,to,"1d");
 }
 /** Operator-configured market-data credential only; never exposed through an HTTP endpoint. */
 int discoveryDailyCandles(String accessToken,String key,LocalDate from,LocalDate to)throws Exception{
  if(accessToken==null||accessToken.isBlank())throw new IllegalStateException("Discovery credential unavailable");
  if(!to.isBefore(LocalDate.now(MarketCalendarService.IST)))throw new IllegalArgumentException("Only completed prior dates are allowed");
  return ingestCandles(accessToken,key,from,to,"1d");
 }
 private int ingestCandles(String accessToken,String key,LocalDate from,LocalDate to,String timeframe)throws Exception{
  if(from.isAfter(to)||from.isBefore(LocalDate.now().minusYears(10)))throw new IllegalArgumentException("Invalid range");
  Long instrument=jdbc.query("SELECT i.id FROM instruments i JOIN exchanges e ON e.id=i.exchange_id JOIN upstox_instrument_map m ON m.exchange_code=e.code AND m.trading_symbol=i.symbol WHERE m.instrument_key=? LIMIT 1",(rs,n)->rs.getLong(1),key).stream().findFirst().orElse(null);
  if(instrument==null)throw new IllegalArgumentException("Instrument registry mapping required");
  String interval=timeframe.equals("1d")?"days/1":timeframe.equals("1minute")?"minutes/1":"minutes/15";
  String url="https://api.upstox.com/v3/historical-candle/"+URLEncoder.encode(key,StandardCharsets.UTF_8)+"/"+interval+"/"+to+"/"+from;
  JsonNode body=json.readTree(http.text(url,accessToken,8_000_000));JsonNode candles=body.path("data").path("candles");
  if(!candles.isArray())throw new IllegalStateException("Invalid candle response");
  long source=jdbc.queryForObject("SELECT id FROM data_sources WHERE source_code='UPSTOX'",Long.class);
  UUID run=jdbc.queryForObject("""
    INSERT INTO ingestion_runs(source_id,job_name,status,started_at,source_revision)
    VALUES (?,'upstox-historical-candles','RUNNING',now(),?) RETURNING id
    """,UUID.class,source,"UPSTOX_API:"+key+":"+timeframe+":"+from+":"+to);
  int count=0,rejected=0;
  for(JsonNode row:candles){
   try{
    if(!row.isArray()||row.size()<6)throw new IllegalArgumentException("INVALID_CANDLE_SHAPE");
    OffsetDateTime timestamp=OffsetDateTime.parse(row.get(0).asText());
    BigDecimal open=row.get(1).decimalValue(),high=row.get(2).decimalValue(),low=row.get(3).decimalValue(),close=row.get(4).decimalValue();
    if(open.signum()<=0||high.signum()<=0||low.signum()<=0||close.signum()<=0||
       high.compareTo(open)<0||high.compareTo(close)<0||high.compareTo(low)<0||
       low.compareTo(open)>0||low.compareTo(close)>0)throw new IllegalArgumentException("INVALID_OHLC");
    if(!row.get(5).canConvertToLong())throw new IllegalArgumentException("INVALID_VOLUME");
    long volume=row.get(5).asLong();if(volume<0)throw new IllegalArgumentException("INVALID_VOLUME");
    LocalDate tradeDate=timestamp.atZoneSameInstant(MarketCalendarService.IST).toLocalDate();
    if(tradeDate.isBefore(from)||tradeDate.isAfter(to))throw new IllegalArgumentException("CANDLE_OUTSIDE_REQUESTED_RANGE");
    int written=jdbc.update("""
      INSERT INTO market_candles(instrument_id,timeframe,candle_time,source_id,ingestion_run_id,open,high,low,close,volume,is_complete,quality_status,adjustment_status)
      VALUES (?,?,?,?,?,?,?,?,?,?,true,'PROVIDER_VALIDATED','RAW_UNADJUSTED')
      ON CONFLICT(instrument_id,timeframe,candle_time) DO UPDATE SET open=EXCLUDED.open,high=EXCLUDED.high,low=EXCLUDED.low,close=EXCLUDED.close,volume=EXCLUDED.volume,source_id=EXCLUDED.source_id,ingestion_run_id=EXCLUDED.ingestion_run_id,quality_status=EXCLUDED.quality_status,received_at=now()
      WHERE market_candles.adjustment_status='RAW_UNADJUSTED' AND market_candles.source_id=EXCLUDED.source_id
      """,instrument,timeframe,java.sql.Timestamp.from(timestamp.toInstant()),source,run,open,high,low,close,volume);
    count+=written;
   }catch(RuntimeException ex){
    rejected++;
    jdbc.update("""
      INSERT INTO data_quality_events(instrument_id,source_id,ingestion_run_id,severity,event_type,details)
      VALUES (?,?,?,'ERROR','PROVIDER_CANDLE_REJECTED',jsonb_build_object('reason',?,'timeframe',?))
      """,instrument,source,run,ex.getMessage(),timeframe);
   }
  }
  jdbc.update("UPDATE ingestion_runs SET status=?,finished_at=now(),records_seen=?,records_written=?,failure_count=? WHERE id=?",
    count>0?"SUCCESS":"FAILED",candles.size(),count,rejected,run);
  if(count==0)throw new IllegalStateException("Provider returned no valid candles");
  jdbc.update("INSERT INTO instrument_source_freshness(instrument_id,source_id,last_synced_at,latest_candle_at) VALUES (?,?,now(),(SELECT max(candle_time) FROM market_candles WHERE instrument_id=? AND timeframe=?)) ON CONFLICT(instrument_id,source_id) DO UPDATE SET last_synced_at=now(),latest_candle_at=EXCLUDED.latest_candle_at",instrument,source,instrument,timeframe);
  return count;
 }
 public int syncHoldings(UUID user)throws Exception{
  JsonNode root=json.readTree(http.text("https://api.upstox.com/v2/portfolio/long-term-holdings",token(user),3_000_000));
  JsonNode rows=root.path("data");if(!rows.isArray())throw new IllegalStateException("Invalid holdings response");
  int count=0;Set<String> received=new HashSet<>();
  for(JsonNode item:rows){
   String symbol=item.path("trading_symbol").asText("");
   if(!symbol.matches("[A-Za-z0-9._&-]{1,50}"))continue;
   BigDecimal quantity=item.path("quantity").decimalValue(),avg=item.path("average_price").decimalValue();
   if(quantity.signum()<=0||avg.signum()<0)continue;
   String normalized=symbol.toUpperCase(Locale.ROOT);received.add(normalized);
   jdbc.update("""
     INSERT INTO personal_holdings(user_id,symbol,asset_type,quantity,average_cost,notes)
     VALUES (?,?,'EQUITY',?,?,'UPSTOX_SYNC')
     ON CONFLICT(user_id,symbol,asset_type) DO UPDATE SET quantity=EXCLUDED.quantity,average_cost=EXCLUDED.average_cost,notes=EXCLUDED.notes,updated_at=now()
     """,user,normalized,quantity,avg);count++;
  }
  // Remove only positions previously created by this broker sync. Manually
  // maintained holdings remain untouched.
  if(received.isEmpty())jdbc.update("DELETE FROM personal_holdings WHERE user_id=? AND notes='UPSTOX_SYNC'",user);
  else jdbc.update("DELETE FROM personal_holdings WHERE user_id=? AND notes='UPSTOX_SYNC' AND symbol NOT IN ("+
    String.join(",",Collections.nCopies(received.size(),"?"))+ ")",
    java.util.stream.Stream.concat(java.util.stream.Stream.of(user),received.stream()).toArray());
  return count;
 }
}

