package com.trading.market;

import com.fasterxml.jackson.databind.*;
import java.time.*;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

/** Date-specific provider evidence, never a weekday-based fabricated calendar.
 * The current installation supports one scheduler. Persistent per-date claims
 * bound retry/restart behavior and existing manual session rows are retained.
 */
@Service
public class ExchangeCalendarSync {
 private static final String BASE="https://api.upstox.com/v2/market/";
 private static final Set<String> VENUES=Set.of("NSE","BSE");
 private static final int BATCH=4;
 private final JdbcTemplate jdbc;
 private final FeedHttp http;
 private final TransactionTemplate tx;
 private final ObjectMapper json=new ObjectMapper();
 @Value("${ATLAS_EXCHANGE_CALENDAR_SYNC_ENABLED:false}") boolean enabled;
 @Value("${MARKET_DATA_USAGE_RIGHTS_CONFIRMED:false}") boolean rights;
 @Value("${MARKET_DATA_ENTITLEMENT_CONFIRMED:false}") boolean entitlement;
 @Value("${UPSTOX_ACCESS_TOKEN:}") String token="";
 public ExchangeCalendarSync(JdbcTemplate jdbc,FeedHttp http,TransactionTemplate tx){
  this.jdbc=jdbc;this.http=http;this.tx=tx;
 }
 public record Session(String exchange,LocalDate date,String type,boolean trading,Instant open,Instant close){}
 private static JsonNode data(JsonNode root){
  if(root==null||!"success".equals(root.path("status").asText())||!root.path("data").isArray()||root.path("data").size()>500)
   throw new IllegalArgumentException("INVALID_CALENDAR_RESPONSE");
  return root.path("data");
 }
 private static Instant stamp(JsonNode node,LocalDate date){
  if(!node.isIntegralNumber()||!node.canConvertToLong())throw new IllegalArgumentException("INVALID_SESSION_TIMESTAMP");
  Instant t=Instant.ofEpochMilli(node.longValue());
  if(!t.atZone(MarketCalendarService.IST).toLocalDate().equals(date))throw new IllegalArgumentException("SESSION_DATE_MISMATCH");
  return t;
 }
 private static Session open(JsonNode row,LocalDate day,boolean special){
  Instant start=stamp(row.path("start_time"),day),end=stamp(row.path("end_time"),day);
  if(!start.isBefore(end))throw new IllegalArgumentException("INVALID_SESSION_BOUNDS");
  boolean weekday=day.getDayOfWeek()!=DayOfWeek.SATURDAY&&day.getDayOfWeek()!=DayOfWeek.SUNDAY;
  boolean regular=!special&&weekday&&start.atZone(MarketCalendarService.IST).toLocalTime().equals(LocalTime.of(9,15))
    &&end.atZone(MarketCalendarService.IST).toLocalTime().equals(LocalTime.of(15,30));
  return new Session(row.path("exchange").asText(),day,regular?"REGULAR":"SPECIAL",true,start,end);
 }
 /** An absent venue or an empty timings list is UNKNOWN, not an attested closure.
  * Explicit holiday data is required for a closed weekday. Multiple/contradictory
  * session records remain unresolved rather than authorizing a regular session.
  */
 static List<Session> parse(LocalDate day,JsonNode timingRoot,JsonNode holidayRoot){
  Map<String,List<Session>> timing=new HashMap<>(),holidayOpen=new HashMap<>();
  Set<String> closed=new HashSet<>(),ambiguous=new HashSet<>();
  for(JsonNode row:data(timingRoot)){
   String venue=row.path("exchange").asText();
   if(!VENUES.contains(venue))continue;
   timing.computeIfAbsent(venue,k->new ArrayList<>()).add(open(row,day,false));
  }
  for(JsonNode row:data(holidayRoot)){
   if(!day.toString().equals(row.path("date").asText()))throw new IllegalArgumentException("HOLIDAY_DATE_MISMATCH");
   String kind=row.path("holiday_type").asText();
   if(!Set.of("TRADING_HOLIDAY","SPECIAL_TIMING","SETTLEMENT_HOLIDAY").contains(kind))
    throw new IllegalArgumentException("UNKNOWN_HOLIDAY_TYPE");
   if("SETTLEMENT_HOLIDAY".equals(kind))continue;
   if(!row.path("closed_exchanges").isArray()||!row.path("open_exchanges").isArray())
    throw new IllegalArgumentException("INVALID_HOLIDAY_VENUES");
   for(JsonNode venue:row.path("closed_exchanges"))if(VENUES.contains(venue.asText())){
    if(!closed.add(venue.asText()))ambiguous.add(venue.asText());
   }
   for(JsonNode value:row.path("open_exchanges")){
    String venue=value.path("exchange").asText();
    if(VENUES.contains(venue))holidayOpen.computeIfAbsent(venue,k->new ArrayList<>()).add(open(value,day,true));
   }
  }
  List<Session> result=new ArrayList<>();
  for(String venue:List.of("NSE","BSE")){
   List<Session> times=timing.getOrDefault(venue,List.of()),special=holidayOpen.getOrDefault(venue,List.of());
   if(ambiguous.contains(venue)||times.size()>1||special.size()>1)continue;
   if(closed.contains(venue)){
    if(times.isEmpty()&&special.isEmpty())result.add(new Session(venue,day,"REGULAR",false,null,null));
    continue;
   }
   if(!special.isEmpty()){
    Session s=special.getFirst();
    if(times.size()==1&&times.getFirst().open().equals(s.open())&&times.getFirst().close().equals(s.close()))result.add(s);
    continue;
   }
   if(times.size()==1)result.add(times.getFirst());
  }
  return List.copyOf(result);
 }
 public List<Session> fetch(LocalDate day,String credential)throws Exception{
  // Both documented date-specific responses must validate before any write.
  JsonNode times=json.readTree(http.text(BASE+"timings/"+day,credential,1_000_000));
  JsonNode holidays=json.readTree(http.text(BASE+"holidays/"+day,credential,1_000_000));
  return parse(day,times,holidays);
 }
 public int store(List<Session> rows){
  return Objects.requireNonNull(tx.execute(status->{
   int writes=0;
   for(Session row:rows){
    // Do not replace manual/other-provider evidence or create a second session
    // type beside a previously imported session for this date.
    writes+=jdbc.update("""
      INSERT INTO market_sessions(exchange_id,session_date,session_type,open_time,close_time,is_trading_day,source_id,source_revision,received_at)
      SELECT e.id,?,?,?,?,?,ds.id,'UPSTOX_MARKET_TIMINGS_HOLIDAYS_V2',now()
      FROM exchanges e CROSS JOIN data_sources ds
      WHERE e.code=? AND ds.source_code='UPSTOX' AND ds.enabled
        AND NOT EXISTS(SELECT 1 FROM market_sessions s WHERE s.exchange_id=e.id AND s.session_date=?)
        AND NOT EXISTS(SELECT 1 FROM exchange_holidays h WHERE h.exchange_code=e.code AND h.holiday_date=? AND ?)
      ON CONFLICT DO NOTHING
      """,row.date(),row.type(),row.open()==null?null:java.sql.Timestamp.from(row.open()),
        row.close()==null?null:java.sql.Timestamp.from(row.close()),row.trading(),row.exchange(),row.date(),row.date(),row.trading());
   }
   return writes;
  }));
 }
 @Scheduled(initialDelayString="${atlas.exchange.calendar.initial-ms:15000}",fixedDelayString="${atlas.exchange.calendar.poll-ms:120000}")
 public void scheduled(){
  if(!enabled||!rights||!entitlement||token.isBlank()||OperatorFeedCooldown.blocked(jdbc))return;
  LocalDate today=LocalDate.now(MarketCalendarService.IST);
  // Most recent dates first, then repair enough calendar days for the
  // 15-month discovery window plus the maximum seven-day prior-session lag. A
  // successful or unresolved date has a persisted cooldown; no hot retries.
  var due=jdbc.query("""
    SELECT CAST(? AS date)-n AS day FROM generate_series(0,470) g(n)
    LEFT JOIN exchange_calendar_attempts a ON a.session_date=CAST(? AS date)-n
    WHERE (a.next_attempt_at IS NULL OR a.next_attempt_at<=now())
      AND (SELECT count(DISTINCT e.code) FROM market_sessions s JOIN exchanges e ON e.id=s.exchange_id
           WHERE s.session_date=CAST(? AS date)-n AND e.code IN ('NSE','BSE'))<2
    ORDER BY n LIMIT ?
    """,(rs,i)->rs.getObject("day",LocalDate.class),today,today,today,BATCH);
  for(LocalDate day:due){
   if(OperatorFeedCooldown.blocked(jdbc))return;
   UUID claim=UUID.randomUUID();
   int acquired=jdbc.update("""
     INSERT INTO exchange_calendar_attempts(session_date,status,claim_id,attempted_at,next_attempt_at)
     VALUES (?,'RUNNING',?,now(),now()+interval '10 minutes')
     ON CONFLICT(session_date) DO UPDATE SET status='RUNNING',claim_id=EXCLUDED.claim_id,
       attempted_at=now(),next_attempt_at=now()+interval '10 minutes',error_code=NULL,rows_written=0
     WHERE exchange_calendar_attempts.next_attempt_at<=now()
     """,day,claim);
   if(acquired!=1)continue;
   try{
    var rows=fetch(day,token);
    int written=store(rows);
    boolean complete=Boolean.TRUE.equals(jdbc.queryForObject("""
       SELECT count(DISTINCT e.code)=2 FROM market_sessions s JOIN exchanges e ON e.id=s.exchange_id
       WHERE s.session_date=? AND e.code IN ('NSE','BSE')
       """,Boolean.class,day));
    finish(day,claim,complete?"SUCCESS":"WAITING_EVIDENCE",written,complete?null:"MISSING_OR_CONFLICTING_SESSION_EVIDENCE",complete?86400:21600);
    if(complete)OperatorFeedCooldown.recovered(jdbc);
   }catch(Exception ex){
    String code=FeedRefreshScheduler.failureCode(ex);
    finish(day,claim,"FAILED",0,code,3600);
    if(ex instanceof InterruptedException){Thread.currentThread().interrupt();return;}
    if(OperatorFeedCooldown.record(jdbc,ex))return;
   }
  }
 }
 private void finish(LocalDate day,UUID claim,String status,int written,String error,int delay){
  jdbc.update("""
    UPDATE exchange_calendar_attempts SET status=?,rows_written=?,error_code=?,claim_id=NULL,
      next_attempt_at=now()+(? * interval '1 second')
    WHERE session_date=? AND claim_id=? AND status='RUNNING'
    """,status,written,error,delay,day,claim);
 }
}
