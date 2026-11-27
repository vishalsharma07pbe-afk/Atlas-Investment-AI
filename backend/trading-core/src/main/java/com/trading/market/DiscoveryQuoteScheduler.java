package com.trading.market;

import com.fasterxml.jackson.databind.*;
import java.math.BigDecimal;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.sql.Timestamp;
import java.time.*;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

/** Public-market prefilter, not a recommendation or a historical candle source. */
@Service
public class DiscoveryQuoteScheduler {
 static final int BATCH=200;
 static final Duration FRESH=Duration.ofMinutes(15);
 private static final BigDecimal TURNOVER_FLOOR=new BigDecimal("10000000");
 private static final BigDecimal MAX_PRICE=new BigDecimal("1000000000");
 private final JdbcTemplate db;
 private final FeedHttp http;
 private final MarketCalendarService calendar;
 private final ObjectMapper json=new ObjectMapper();
 @Value("${ATLAS_DISCOVERY_QUOTE_SCREEN_ENABLED:false}") boolean enabled;
 @Value("${MARKET_DATA_USAGE_RIGHTS_CONFIRMED:false}") boolean rights;
 @Value("${MARKET_DATA_ENTITLEMENT_CONFIRMED:false}") boolean entitlement;
 @Value("${UPSTOX_ACCESS_TOKEN:}") String token="";
 public DiscoveryQuoteScheduler(JdbcTemplate db,FeedHttp http,MarketCalendarService calendar){
  this.db=db;this.http=http;this.calendar=calendar;
 }
 record Identity(long id,String key,String isin,String symbol){}
 record Observation(Instant trade,Instant response,BigDecimal price,BigDecimal previous,long volume,
                    BigDecimal turnover,Double spread,double change,boolean priority){}
 @Scheduled(initialDelayString="${atlas.discovery.quote.initial-ms:45000}",fixedDelayString="${atlas.discovery.quote.poll-ms:30000}")
 public void scheduled(){
  if(!enabled||!rights||!entitlement||token.isBlank())return;
  for(String exchange:List.of("NSE","BSE")){
   if(OperatorFeedCooldown.blocked(db))return;
   Instant now=Instant.now();
   var context=calendar.sessionContext(exchange,now);
   if(!"MARKET_HOURS".equals(context.get("phase")))continue;
   try{
    if(!refresh(exchange,Instant.parse((String)context.get("open_at")),Instant.parse((String)context.get("close_at"))))return;
    // One batch per venue, sequential, never fan out concurrent requests.
    Thread.sleep(1000);
   }catch(InterruptedException ex){Thread.currentThread().interrupt();return;}
  }
 }
 @Scheduled(initialDelayString="${atlas.discovery.activity.cleanup.initial-ms:120000}",fixedDelayString="${atlas.discovery.activity.cleanup.poll-ms:21600000}")
 public void pruneActivity(){
  db.update("DELETE FROM discovery_activity_day WHERE session_date < (now() AT TIME ZONE 'Asia/Kolkata')::date-45");
 }
 boolean refresh(String exchange,Instant open,Instant close){
  if(!Set.of("NSE","BSE").contains(exchange))throw new IllegalArgumentException("exchange");
  if(OperatorFeedCooldown.blocked(db))return false;
  Instant now=Instant.now();
  if(now.isBefore(open)||!now.isBefore(close))return true;
  var rows=db.queryForList("""
    SELECT u.instrument_id,u.instrument_key,u.isin,u.symbol
    FROM discovery_quote_universe u LEFT JOIN discovery_security_context quality ON quality.instrument_id=u.instrument_id
    LEFT JOIN discovery_quote_screen q ON q.instrument_id=u.instrument_id
       AND q.instrument_key=u.instrument_key AND q.isin=u.isin
    WHERE u.exchange=? AND coalesce(quality.security_state,'UNKNOWN')<>'SUSPENDED_REPORTED' AND (q.attempted_at IS NULL OR q.attempted_at<=now()-interval '30 seconds')
    ORDER BY q.attempted_at ASC NULLS FIRST,u.instrument_id LIMIT 200
    """,exchange);
  Map<String,Identity> claimed=new LinkedHashMap<>();
  Timestamp attempt=Timestamp.from(now);
  for(var row:rows){
   Identity i=new Identity(((Number)row.get("instrument_id")).longValue(),(String)row.get("instrument_key"),
     (String)row.get("isin"),(String)row.get("symbol"));
   if(!UpstoxFeedService.validEquityIdentity(exchange,i.key(),i.isin()))continue;
   int n=db.update("""
     INSERT INTO discovery_quote_screen(instrument_id,instrument_key,isin,attempted_at,state)
     VALUES (?,?,?,?,'PENDING')
     ON CONFLICT(instrument_id) DO UPDATE SET instrument_key=excluded.instrument_key,isin=excluded.isin,
       attempted_at=excluded.attempted_at,state='PENDING',observed_at=NULL,response_at=NULL,
       last_price=NULL,previous_close=NULL,session_volume=NULL,turnover_proxy=NULL,spread_percent=NULL,day_change_percent=NULL
     WHERE discovery_quote_screen.attempted_at<=excluded.attempted_at-interval '30 seconds'
     """,i.id(),i.key(),i.isin(),attempt);
   if(n==1)claimed.put(i.key(),i);
  }
  if(claimed.isEmpty())return true;
  try{
   if(OperatorFeedCooldown.blocked(db)||!Instant.now().isBefore(close)){finish(claimed,attempt,"FAILED");return false;}
   String url="https://api.upstox.com/v3/market-quote/quotes?instrument_key="+
     URLEncoder.encode(String.join(",",claimed.keySet()),StandardCharsets.UTF_8);
   JsonNode body=json.readTree(http.text(url,token,4_000_000));
   Instant received=Instant.now();
   var parsed=validateEnvelope(body,claimed);
   for(var i:claimed.values()){
    JsonNode q=parsed.get(i.key());
    Observation o=q==null?null:parse(q,i,open,close,received);
    if(o==null){finish(Map.of(i.key(),i),attempt,q==null?"MISSING":"INVALID");continue;}
    boolean lateSession=!o.trade().isBefore(close.minus(Duration.ofMinutes(90)));
    // Preserve the last valid intraday activity observation per session even
    // when a later attempt fails. Never use this table as completed OHLCV.
    db.update("""
      WITH accepted AS (
        UPDATE discovery_quote_screen SET state=?,observed_at=?,response_at=?,last_price=?,previous_close=?,
          session_volume=?,turnover_proxy=?,spread_percent=?,day_change_percent=?
        WHERE instrument_id=? AND instrument_key=? AND isin=? AND attempted_at=? AND state='PENDING'
        RETURNING instrument_id,instrument_key,isin,observed_at,response_at,session_volume,turnover_proxy,spread_percent,day_change_percent
      )
      INSERT INTO discovery_activity_day(instrument_id,instrument_key,isin,session_date,observed_at,response_at,
        session_volume,turnover_proxy,spread_percent,day_change_percent,late_session)
      SELECT instrument_id,instrument_key,isin,(observed_at AT TIME ZONE 'Asia/Kolkata')::date,
        observed_at,response_at,session_volume,turnover_proxy,spread_percent,day_change_percent,?
      FROM accepted WHERE true
      ON CONFLICT(instrument_id,session_date) DO UPDATE SET
        instrument_key=excluded.instrument_key,isin=excluded.isin,observed_at=excluded.observed_at,
        response_at=excluded.response_at,session_volume=excluded.session_volume,turnover_proxy=excluded.turnover_proxy,
        spread_percent=excluded.spread_percent,day_change_percent=excluded.day_change_percent,late_session=excluded.late_session
      WHERE (excluded.observed_at,excluded.response_at)>(discovery_activity_day.observed_at,discovery_activity_day.response_at)
      """,o.priority()?"PRIORITY":"OBSERVED",Timestamp.from(o.trade()),Timestamp.from(o.response()),o.price(),
      o.previous(),o.volume(),o.turnover(),o.spread(),o.change(),i.id(),i.key(),i.isin(),attempt,lateSession);
   }
   OperatorFeedCooldown.recovered(db);
   return true;
  }catch(InterruptedException ex){
   Thread.currentThread().interrupt();finish(claimed,attempt,"FAILED");return false;
  }catch(Exception ex){
   finish(claimed,attempt,"FAILED");
   OperatorFeedCooldown.record(db,ex);
   return false;
  }
 }
 private void finish(Map<String,Identity> batch,Timestamp attempt,String state){
  for(var i:batch.values())db.update("""
     UPDATE discovery_quote_screen SET state=? WHERE instrument_id=? AND instrument_key=? AND isin=? AND attempted_at=? AND state='PENDING'
     """,state,i.id(),i.key(),i.isin(),attempt);
 }
 static Map<String,JsonNode> validateEnvelope(JsonNode body,Map<String,Identity> requested){
  if(requested.isEmpty()||requested.size()>BATCH||body==null||!"success".equals(body.path("status").asText())
     ||!body.path("data").isObject()||body.path("data").size()>requested.size())throw new IllegalStateException("INVALID_BULK_QUOTE");
  Map<String,JsonNode> result=new HashMap<>();
  for(JsonNode q:body.path("data")){
   String key=q.path("instrument_token").asText("");
   if(!requested.containsKey(key)||result.putIfAbsent(key,q)!=null)throw new IllegalStateException("INVALID_BULK_IDENTITY");
  }
  return result;
 }
 static BigDecimal positive(JsonNode n){
  if(!n.isNumber())return null;
  BigDecimal v=n.decimalValue();
  return v.signum()>0&&v.compareTo(MAX_PRICE)<=0?v:null;
 }
 static Observation parse(JsonNode q,Identity i,Instant open,Instant close,Instant received){
  try{
   if(!i.key().equals(q.path("instrument_token").asText())||!i.symbol().equals(q.path("symbol").asText()))return null;
   String tradeRaw=q.path("last_trade_time").asText("");
   if(!tradeRaw.matches("[0-9]{13}"))return null;
   Instant trade=Instant.ofEpochMilli(Long.parseLong(tradeRaw));
   Instant response=OffsetDateTime.parse(q.path("timestamp").asText()).toInstant();
   if(trade.isBefore(open)||!trade.isBefore(close)||trade.isAfter(response)||trade.isBefore(received.minus(FRESH))
     ||response.isAfter(received.plusSeconds(5))||response.isBefore(received.minus(FRESH))||trade.isAfter(received))return null;
   BigDecimal price=positive(q.path("last_price")),previous=positive(q.path("prev_close_price")),avg=positive(q.path("average_price"));
   JsonNode volumeNode=q.path("volume");
   if(price==null||previous==null||avg==null||!volumeNode.isIntegralNumber()||!volumeNode.canConvertToLong())return null;
   long volume=volumeNode.longValue();
   if(volume<=0||volume>1_000_000_000_000L)return null;
   BigDecimal turnover=avg.multiply(BigDecimal.valueOf(volume));
   BigDecimal bid=positive(q.path("depth").path("buy").path(0).path("price"));
   BigDecimal ask=positive(q.path("depth").path("sell").path(0).path("price"));
   Double spread=bid!=null&&ask!=null&&ask.compareTo(bid)>=0?200*(ask.doubleValue()-bid.doubleValue())/(ask.doubleValue()+bid.doubleValue()):null;
   double change=100*(price.doubleValue()/previous.doubleValue()-1);
   if(!Double.isFinite(change))return null;
   // Only a provisional activity priority, not a safety or fundamental gate.
   // Low-volume/one-sided stocks still rotate and are not permanently excluded.
   boolean priority=turnover.compareTo(TURNOVER_FLOOR)>=0&&spread!=null&&spread<=1&&Math.abs(change)<10;
   return new Observation(trade,response,price,previous,volume,turnover,spread,change,priority);
  }catch(RuntimeException ex){return null;}
 }
}
