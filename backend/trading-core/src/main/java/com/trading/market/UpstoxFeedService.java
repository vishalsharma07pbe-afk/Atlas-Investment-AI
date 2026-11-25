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
import org.springframework.transaction.annotation.Transactional;
@Service public class UpstoxFeedService {
 private final JdbcTemplate jdbc;private final FeedHttp http;private final VersionedVaultReader vault;
 private final ObjectMapper json=new ObjectMapper();
 public UpstoxFeedService(JdbcTemplate jdbc,FeedHttp http,VersionedVaultReader vault){this.jdbc=jdbc;this.http=http;this.vault=vault;}
 private static final String MASTER="https://assets.upstox.com/market-quote/instruments/exchange/";
 @Transactional(rollbackFor=Exception.class)
 public int syncMaster()throws Exception{
  int count=0;
  for(String exchange:List.of("NSE","BSE")){
   // NSE's valid decompressed BOD JSON is currently larger than 40 MB. Keep a
   // strict ceiling, then retain only cash-equity identifiers used by holdings.
   JsonNode root=json.readTree(http.get(MASTER+exchange+".json.gz",null,60_000_000));
   if(!root.isArray()||root.isEmpty())throw new IllegalStateException("Invalid instrument master");
   int accepted=0;
   Set<String> seen=new HashSet<>();
   for(JsonNode item:root){
    String key=item.path("instrument_key").asText(""),symbol=item.path("trading_symbol").asText("");
    String type=item.path("instrument_type").asText("");
    boolean equity=Set.of("EQ","EQUITY").contains(type)||("BSE".equals(exchange)&&Set.of("A","B").contains(type));
    if(!equity||
       !exchange.equals(item.path("exchange").asText(""))||!symbol.matches("[A-Za-z0-9._&-]{1,50}"))continue;
    String displayName=item.path("name").asText(item.path("short_name").asText(""));
    if(displayName.isBlank())displayName=null;
    else if(displayName.length()>240)displayName=displayName.substring(0,240);
    String isin=item.path("isin").asText("");
    if(!validEquityIdentity(exchange,key,isin))continue;
    if(key.matches("BSE_EQ[|][0-9]{1,10}")&&!key.equals("BSE_EQ|"+item.path("exchange_token").asText("")))continue;
    if(!seen.add(key))throw new IllegalStateException("Duplicate provider instrument identity");
    // Do not relabel existing historical observations to a different security.
    int mapped=jdbc.update("""
      INSERT INTO instruments(exchange_id,symbol,series,isin,security_name,instrument_type,
        listing_status,active,source,source_revision,updated_at)
      VALUES ((SELECT id FROM exchanges WHERE code=?),?,'EQ',?,?,?,'ACTIVE',true,
        'UPSTOX','UPSTOX_INSTRUMENT_MASTER',now())
      ON CONFLICT(exchange_id,symbol,series) DO UPDATE SET
        isin=EXCLUDED.isin,security_name=COALESCE(EXCLUDED.security_name,instruments.security_name),
        instrument_type=EXCLUDED.instrument_type,listing_status='ACTIVE',active=true,
        source='UPSTOX',source_revision='UPSTOX_INSTRUMENT_MASTER',updated_at=now()
      WHERE instruments.isin=EXCLUDED.isin OR (instruments.isin IS NULL AND NOT EXISTS(
        SELECT 1 FROM market_candles c WHERE c.instrument_id=instruments.id))
      """,exchange,symbol,isin,displayName,"EQ");
    if(mapped!=1)continue;
    int written=jdbc.update("""
      INSERT INTO upstox_instrument_map(instrument_key,exchange_code,isin,trading_symbol,instrument_type,display_name)
      VALUES (?,?,?,?,?,?)
      ON CONFLICT(instrument_key) DO UPDATE SET isin=EXCLUDED.isin,trading_symbol=EXCLUDED.trading_symbol,
        instrument_type=EXCLUDED.instrument_type,display_name=EXCLUDED.display_name,updated_at=now()
      WHERE upstox_instrument_map.exchange_code=EXCLUDED.exchange_code
        AND (upstox_instrument_map.isin IS NULL OR upstox_instrument_map.isin=EXCLUDED.isin)
      """,key,exchange,isin,symbol,"EQ",displayName);
    if(written!=1)throw new IllegalStateException("Provider instrument identity conflict");
    count++;accepted++;
   }
   if(accepted==0)throw new IllegalStateException("No verified equity mappings in instrument master");
  }
  return count;
 }
 static boolean validEquityIdentity(String exchange,String key,String isin){
  return isin.matches("IN[A-Z0-9]{10}") && (
    ("NSE".equals(exchange)&&key.equals("NSE_EQ|"+isin))||
    ("BSE".equals(exchange)&&(key.equals("BSE_EQ|"+isin)||key.matches("BSE_EQ\\|[0-9]{1,10}"))));
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
  if(!Integer.valueOf(1).equals(jdbc.queryForObject("""
      SELECT count(*) FROM upstox_instrument_map m JOIN exchanges e ON e.code=m.exchange_code
      JOIN instruments i ON i.exchange_id=e.id AND i.symbol=m.trading_symbol AND i.isin=m.isin
      WHERE m.instrument_key=? AND m.isin ~ '^IN[A-Z0-9]{10}$' AND m.instrument_type IN ('EQ','EQUITY')
        AND i.active AND i.series='EQ' AND i.listing_status='ACTIVE'
        AND i.instrument_type IN ('EQ','EQUITY','STOCK')
      """,Integer.class,key)))throw new IllegalArgumentException("Exact equity registry mapping required");
  String url="https://api.upstox.com/v3/market-quote/quotes?instrument_key="+URLEncoder.encode(key,StandardCharsets.UTF_8);
  JsonNode body=json.readTree(http.text(url,token(user),2_000_000));
  if(!"success".equals(body.path("status").asText()))throw new IllegalStateException("Provider rejected quote");
  JsonNode data=body.path("data");
  if(!data.isObject()||data.size()!=1)throw new IllegalStateException("Invalid quote response");
  JsonNode quote=data.elements().next();
  if(!key.equals(quote.path("instrument_token").asText(""))||!quote.path("last_price").isNumber())
    throw new IllegalStateException("Quote identity or price invalid");
  BigDecimal ltp=quote.path("last_price").decimalValue();
  if(ltp.signum()<=0)throw new IllegalStateException("Invalid price");
  // The V3 timestamp is response generation time, not last trade time.
  Instant received=Instant.now(),timestamp,responseTime;
  try{
    String tradeTime=quote.path("last_trade_time").asText("");
    if(!tradeTime.matches("[0-9]{13}"))throw new IllegalArgumentException();
    timestamp=Instant.ofEpochMilli(Long.parseLong(tradeTime));
    responseTime=OffsetDateTime.parse(quote.path("timestamp").asText()).toInstant();
    if(timestamp.isAfter(received)||timestamp.isAfter(responseTime)||responseTime.isAfter(received.plusSeconds(5)))
      throw new IllegalArgumentException();
  }catch(RuntimeException ex){throw new IllegalStateException("Provider quote timestamp invalid");}
  BigDecimal previousClose=quote.path("prev_close_price").isNumber()?quote.path("prev_close_price").decimalValue():null;
  if(previousClose!=null&&previousClose.signum()<=0)previousClose=null;
  jdbc.update("""
    INSERT INTO upstox_market_quotes(instrument_key,ltp,source_code,quoted_at) VALUES (?,?,'UPSTOX',?)
    ON CONFLICT(instrument_key) DO UPDATE SET ltp=EXCLUDED.ltp,quoted_at=EXCLUDED.quoted_at,received_at=now()
    WHERE upstox_market_quotes.quoted_at<EXCLUDED.quoted_at
    """,key,ltp,java.sql.Timestamp.from(timestamp));
  var result=json.createObjectNode().put("instrument_key",key).put("ltp",ltp).put("as_of",timestamp.toString())
    .put("received_at",received.toString()).put("source","UPSTOX").put("timestamp_basis","LAST_TRADE_TIME");
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
 /** Current-session operator research, completed bars only; no user vault access. */
 int discoveryIntradayCandles(String accessToken,String key,Instant cutoff)throws Exception{
  if(accessToken==null||accessToken.isBlank())throw new IllegalStateException("Discovery credential unavailable");
  LocalDate day=cutoff.atZone(MarketCalendarService.IST).toLocalDate();
  return ingestCandles(accessToken,key,day,day,"15minute",cutoff);
 }
 private int ingestCandles(String accessToken,String key,LocalDate from,LocalDate to,String timeframe)throws Exception{
  return ingestCandles(accessToken,key,from,to,timeframe,null);
 }
 private int ingestCandles(String accessToken,String key,LocalDate from,LocalDate to,String timeframe,Instant cutoff)throws Exception{
  LocalDate today=LocalDate.now(MarketCalendarService.IST);
  if(from.isAfter(to)||from.isBefore(today.minusYears(10))||to.isAfter(today)||("1d".equals(timeframe)&&!to.isBefore(today)))throw new IllegalArgumentException("Invalid or incomplete date range");
  List<Long> mapped=jdbc.query("""
    SELECT i.id FROM instruments i JOIN exchanges e ON e.id=i.exchange_id
    JOIN upstox_instrument_map m ON m.exchange_code=e.code AND m.trading_symbol=i.symbol AND m.isin=i.isin
    WHERE m.instrument_key=? AND m.isin ~ '^IN[A-Z0-9]{10}$'
      AND m.instrument_type IN ('EQ','EQUITY') AND i.series='EQ' AND i.active
      AND i.listing_status='ACTIVE' AND i.instrument_type IN ('EQ','EQUITY','STOCK')
    """,(rs,n)->rs.getLong(1),key);
  if(mapped.size()!=1)throw new IllegalArgumentException("Exact equity registry mapping required");
  long instrument=mapped.getFirst();
  String interval=timeframe.equals("1d")?"days/1":timeframe.equals("1minute")?"minutes/1":"minutes/15";
  String url="https://api.upstox.com/v3/historical-candle/"+(cutoff==null?"":"intraday/")+URLEncoder.encode(key,StandardCharsets.UTF_8)+"/"+interval+(cutoff==null?"/"+to+"/"+from:"");
  JsonNode body=json.readTree(http.text(url,accessToken,8_000_000));JsonNode candles=body.path("data").path("candles");
  if(!candles.isArray()||!"success".equals(body.path("status").asText()))throw new IllegalStateException("Invalid candle response");
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
    if(cutoff!=null){
     var start=timestamp.atZoneSameInstant(MarketCalendarService.IST);
     LocalTime t=start.toLocalTime();
     if(!start.toLocalDate().equals(from)||t.isBefore(LocalTime.of(9,15))||!t.isBefore(LocalTime.of(15,30))
        ||t.getMinute()%15!=0||t.getSecond()!=0||t.getNano()!=0||!row.get(5).isIntegralNumber())throw new IllegalArgumentException("INVALID_SESSION_BAR");
     if(timestamp.toInstant().plusSeconds(15*60).isAfter(cutoff))continue;
     for(int j=1;j<=4;j++)if(!row.get(j).isNumber())throw new IllegalArgumentException("INVALID_OHLC");
    }
    // Manual history also must not overwrite a forming intraday bar as complete.
    if(cutoff==null&&!timeframe.equals("1d")&&timestamp.toInstant()
        .plusSeconds(timeframe.equals("1minute")?60:900).isAfter(Instant.now()))continue;
    for(int j=1;j<=4;j++)if(!row.get(j).isNumber())throw new IllegalArgumentException("INVALID_OHLC");
    BigDecimal open=row.get(1).decimalValue(),high=row.get(2).decimalValue(),low=row.get(3).decimalValue(),close=row.get(4).decimalValue();
    if(open.signum()<=0||high.signum()<=0||low.signum()<=0||close.signum()<=0||
       high.compareTo(open)<0||high.compareTo(close)<0||high.compareTo(low)<0||
       low.compareTo(open)>0||low.compareTo(close)>0)throw new IllegalArgumentException("INVALID_OHLC");
    if(!row.get(5).isIntegralNumber()||!row.get(5).canConvertToLong())throw new IllegalArgumentException("INVALID_VOLUME");
    long volume=row.get(5).asLong();if(volume<0)throw new IllegalArgumentException("INVALID_VOLUME");
    LocalDate tradeDate=timestamp.atZoneSameInstant(MarketCalendarService.IST).toLocalDate();
    if(tradeDate.isBefore(from)||tradeDate.isAfter(to))throw new IllegalArgumentException("CANDLE_OUTSIDE_REQUESTED_RANGE");
    int written=jdbc.update("""
      INSERT INTO market_candles(instrument_id,timeframe,candle_time,source_id,ingestion_run_id,open,high,low,close,volume,is_complete,quality_status,adjustment_status)
      VALUES (?,?,?,?,?,?,?,?,?,?,true,'PROVIDER_VALIDATED','RAW_UNADJUSTED')
      ON CONFLICT(instrument_id,timeframe,candle_time) DO UPDATE SET open=EXCLUDED.open,high=EXCLUDED.high,low=EXCLUDED.low,close=EXCLUDED.close,volume=EXCLUDED.volume,source_id=EXCLUDED.source_id,ingestion_run_id=EXCLUDED.ingestion_run_id,quality_status=EXCLUDED.quality_status,is_complete=true,received_at=now()
      WHERE market_candles.adjustment_status='RAW_UNADJUSTED' AND market_candles.source_id=EXCLUDED.source_id
      """,instrument,timeframe,java.sql.Timestamp.from(timestamp.toInstant()),source,run,open,high,low,close,volume);
    count+=written;
   }catch(RuntimeException ex){
    rejected++;
    jdbc.update("""
      INSERT INTO data_quality_events(instrument_id,source_id,ingestion_run_id,severity,event_type,details)
      VALUES (?,?,?,'ERROR','PROVIDER_CANDLE_REJECTED',jsonb_build_object('reason',?,'timeframe',?))
      """,instrument,source,run,"INVALID_OR_UNWRITABLE_CANDLE",timeframe);
   }
  }
  jdbc.update("UPDATE ingestion_runs SET status=?,finished_at=now(),records_seen=?,records_written=?,failure_count=? WHERE id=?",
    count>0?"SUCCESS":"FAILED",candles.size(),count,rejected,run);
  if(count==0)throw new IllegalStateException("Provider returned no valid candles");
  jdbc.update("INSERT INTO instrument_source_freshness(instrument_id,source_id,last_synced_at,latest_candle_at) VALUES (?,?,now(),(SELECT max(candle_time) FROM market_candles WHERE instrument_id=? AND timeframe=?)) ON CONFLICT(instrument_id,source_id) DO UPDATE SET last_synced_at=now(),latest_candle_at=EXCLUDED.latest_candle_at",instrument,source,instrument,timeframe);
  return count;
 }
 @Transactional(rollbackFor=Exception.class)
 public int syncHoldings(UUID user)throws Exception{
  UUID locked=jdbc.queryForObject("SELECT id FROM atlas_users WHERE id=? FOR UPDATE",UUID.class,user);
  if(!user.equals(locked))throw new IllegalStateException("Holding owner unavailable");
  JsonNode root=json.readTree(http.text("https://api.upstox.com/v2/portfolio/long-term-holdings",token(user),3_000_000));
  JsonNode rows=root.path("data");
  if(!"success".equals(root.path("status").asText())||!rows.isArray()||rows.size()>2000)
    throw new IllegalStateException("Invalid holdings response");
  record Holding(String symbol,BigDecimal quantity,BigDecimal average){}
  List<Holding> verified=new ArrayList<>();
  Set<String> received=new HashSet<>(),identities=new HashSet<>();
  for(JsonNode item:rows){
   String symbol=item.path("trading_symbol").asText("").toUpperCase(Locale.ROOT);
   String isin=item.path("isin").asText(""),exchange=item.path("exchange").asText(""),key=item.path("instrument_token").asText("");
   JsonNode qty=item.path("quantity"),price=item.path("average_price");
   if(!symbol.matches("[A-Z0-9._&-]{1,50}")||!validEquityIdentity(exchange,key,isin)||
       !qty.isIntegralNumber()||!qty.canConvertToInt()||qty.asInt()<=0||!price.isNumber()||
       price.decimalValue().signum()<0||price.decimalValue().compareTo(new BigDecimal("100000000000000"))>=0||
       !received.add(symbol)||!identities.add(isin))
     throw new IllegalStateException("Incomplete or ambiguous holdings response");
   Integer matches=jdbc.queryForObject("""
     SELECT count(*) FROM upstox_instrument_map m
     JOIN exchanges e ON e.code=m.exchange_code JOIN instruments i
       ON i.exchange_id=e.id AND i.symbol=m.trading_symbol AND i.isin=m.isin
     WHERE m.instrument_key=? AND m.exchange_code=? AND m.isin=? AND upper(m.trading_symbol)=?
       AND m.instrument_type IN ('EQ','EQUITY') AND i.series='EQ' AND i.active
       AND i.listing_status='ACTIVE' AND i.instrument_type IN ('EQ','EQUITY','STOCK')
       AND NOT EXISTS(SELECT 1 FROM instruments other JOIN exchanges venue ON venue.id=other.exchange_id
         WHERE venue.code IN ('NSE','BSE') AND upper(other.symbol)=? AND other.active
           AND other.series='EQ' AND other.listing_status='ACTIVE' AND other.isin IS DISTINCT FROM m.isin)
     """,Integer.class,key,exchange,isin,symbol,symbol);
   if(!Integer.valueOf(1).equals(matches))throw new IllegalStateException("Exact holding identity unavailable");
   verified.add(new Holding(symbol,qty.decimalValue(),price.decimalValue()));
  }
  int count=0;
  for(Holding h:verified){
   int written=jdbc.update("""
     INSERT INTO personal_holdings(user_id,symbol,asset_type,quantity,average_cost,notes)
     VALUES (?,?,'EQUITY',?,?,'UPSTOX_SYNC')
     ON CONFLICT(user_id,symbol,asset_type) DO UPDATE SET quantity=EXCLUDED.quantity,
       average_cost=EXCLUDED.average_cost,notes=EXCLUDED.notes,updated_at=now()
     WHERE personal_holdings.notes='UPSTOX_SYNC'
     """,user,h.symbol(),h.quantity(),h.average());
   if(written!=1)throw new IllegalStateException("Manual holding conflict; reconciliation required");
   count+=written;
  }
  // Only a completely validated successful response can reconcile positions.
  if(received.isEmpty())jdbc.update("DELETE FROM personal_holdings WHERE user_id=? AND asset_type='EQUITY' AND notes='UPSTOX_SYNC'",user);
  else jdbc.update("DELETE FROM personal_holdings WHERE user_id=? AND asset_type='EQUITY' AND notes='UPSTOX_SYNC' AND symbol NOT IN ("+
    String.join(",",Collections.nCopies(received.size(),"?"))+ ")",
    java.util.stream.Stream.concat(java.util.stream.Stream.of(user),received.stream()).toArray());
  return count;
 }
}
