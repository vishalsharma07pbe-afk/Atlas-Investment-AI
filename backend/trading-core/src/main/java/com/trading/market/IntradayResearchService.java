package com.trading.market;

import java.time.*;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

/** Research-only, bounded completed-session observations. */
@Service
public class IntradayResearchService {
 private final JdbcTemplate jdbc;
 private final UpstoxFeedService stocks;
 private final MarketCalendarService calendar;
 private final IntradayScenarioLedger scenarios;
 @Value("${ATLAS_INTRADAY_RESEARCH_ENABLED:false}") boolean enabled;
 @Value("${MARKET_DATA_USAGE_RIGHTS_CONFIRMED:false}") boolean rights;
 @Value("${MARKET_DATA_ENTITLEMENT_CONFIRMED:false}") boolean entitlement;
 @Value("${UPSTOX_ACCESS_TOKEN:}") String token="";
 public IntradayResearchService(JdbcTemplate jdbc,UpstoxFeedService stocks,MarketCalendarService calendar){
  this.jdbc=jdbc;this.stocks=stocks;this.calendar=calendar;this.scenarios=new IntradayScenarioLedger(jdbc,calendar);
 }
 boolean permitted(){return enabled&&rights&&entitlement&&!token.isBlank();}

 @Scheduled(initialDelayString="${atlas.intraday.initial-ms:30000}",fixedDelayString="${atlas.intraday.poll-ms:60000}")
 public void scheduled(){
  if(!permitted())return;
  Instant now=Instant.now();
  boolean open=false;
  for(String exchange:List.of("NSE","BSE"))if(calendar.isMarketOpen(exchange,now)){open=true;refreshExchange(exchange,now);}
  // Scenario validation is local; final capture is separately bounded.
  // GET is read-only.
  try{
   Instant captured=Instant.now();
   if(open)scenarios.publish(current(captured,false),captured);
   if(!open)for(String exchange:List.of("NSE","BSE"))refreshAfterClose(exchange,captured);
   scenarios.settle(Instant.now());
   var local=captured.atZone(MarketCalendarService.IST).toLocalTime();
   if(!open&&!local.isBefore(LocalTime.of(15,30))&&local.isBefore(LocalTime.of(17,0)))scenarios.replayOne(captured);
  }catch(org.springframework.dao.DataAccessException|IllegalStateException ex){
   // Optional scenario evidence must not break the existing feed.
   org.slf4j.LoggerFactory.getLogger(IntradayResearchService.class).warn("Intraday scenario evidence unavailable: {}",ex.getClass().getSimpleName());
  }
 }

 /** Complete the final bar only for the already collected daily sample.
  * One call per venue/pass, at most eight listings and two attempts each;
  * no historical backfill, no bypass of the shared credential cooldown.
  */
 void refreshAfterClose(String exchange,Instant now){
  if(!permitted())return;
  LocalDate day=now.atZone(MarketCalendarService.IST).toLocalDate();
  Instant close=IntradayScenario.end(day);
  if(now.isBefore(close.plusSeconds(60))||!now.isBefore(close.plusSeconds(2700)))return;
  if(!IntradayScenario.regular(calendar.sessionContext(exchange,now),day)||OperatorFeedCooldown.blocked(jdbc))return;
  var due=jdbc.queryForList("""
    WITH sampled AS (
     SELECT a.instrument_id,m.instrument_key,
       EXISTS(SELECT 1 FROM intraday_scenario_watch w WHERE w.session_date=? AND w.instrument_id=a.instrument_id) AS watched
     FROM intraday_research_attempts a JOIN discovery_quote_universe m ON m.instrument_id=a.instrument_id
     LEFT JOIN discovery_security_context sc ON sc.instrument_id=m.instrument_id AND sc.isin=m.isin AND sc.instrument_key=m.instrument_key
     WHERE m.exchange=? AND a.status='SUCCESS'
       AND a.attempted_at>=? AND a.attempted_at<?
       AND coalesce(sc.security_state,'UNKNOWN') IN ('NORMAL','UNKNOWN')
     ORDER BY watched DESC,a.instrument_id LIMIT 8
    )
    SELECT s.instrument_id,s.instrument_key FROM sampled s
    LEFT JOIN intraday_final_capture f ON f.instrument_id=s.instrument_id AND f.session_date=?
    WHERE (f.instrument_id IS NULL OR (f.attempts<2 AND f.next_attempt_at<=now() AND f.status<>'COMPLETE'))
     AND NOT EXISTS (
       SELECT 1 FROM market_candles c JOIN data_sources ds ON ds.id=c.source_id
       WHERE c.instrument_id=s.instrument_id AND c.timeframe='15minute' AND c.candle_time=?
        AND c.is_complete AND c.quality_status='PROVIDER_VALIDATED' AND c.adjustment_status='RAW_UNADJUSTED' AND ds.source_code='UPSTOX')
    ORDER BY s.watched DESC,f.next_attempt_at NULLS FIRST,s.instrument_id LIMIT 1
    """,day,exchange,java.sql.Timestamp.from(IntradayScenario.start(day)),java.sql.Timestamp.from(close),day,java.sql.Timestamp.from(close.minusSeconds(900)));
  for(var row:due){
   long id=((Number)row.get("instrument_id")).longValue();
   int claimed=jdbc.update("""
     INSERT INTO intraday_final_capture(instrument_id,session_date,attempts,next_attempt_at,status)
     VALUES (?,?,1,now()+interval '10 minutes','RUNNING')
     ON CONFLICT(instrument_id,session_date) DO UPDATE SET attempts=intraday_final_capture.attempts+1,
       next_attempt_at=now()+interval '10 minutes',status='RUNNING'
     WHERE intraday_final_capture.attempts<2 AND intraday_final_capture.next_attempt_at<=now() AND intraday_final_capture.status<>'COMPLETE'
     """,id,day);
   if(claimed!=1)continue;
   try{
    int written=stocks.discoveryIntradayCandles(token,(String)row.get("instrument_key"),now);
    boolean complete=Boolean.TRUE.equals(jdbc.queryForObject("""
      SELECT EXISTS(SELECT 1 FROM market_candles c JOIN data_sources ds ON ds.id=c.source_id
       WHERE c.instrument_id=? AND c.timeframe='15minute' AND c.candle_time=? AND c.is_complete
        AND c.quality_status='PROVIDER_VALIDATED' AND c.adjustment_status='RAW_UNADJUSTED' AND ds.source_code='UPSTOX')
      """,Boolean.class,id,java.sql.Timestamp.from(close.minusSeconds(900))));
    jdbc.update("UPDATE intraday_final_capture SET status=? WHERE instrument_id=? AND session_date=? AND status='RUNNING'",
       complete?"COMPLETE":"MISSING_FINAL_BAR",id,day);
    if(written>0)OperatorFeedCooldown.recovered(jdbc);
   }catch(Exception ex){
    jdbc.update("UPDATE intraday_final_capture SET status='FAILED' WHERE instrument_id=? AND session_date=? AND status='RUNNING'",id,day);
    OperatorFeedCooldown.record(jdbc,ex);
   }
  }
 }
 void refreshExchange(String exchange,Instant now){
  if(OperatorFeedCooldown.blocked(jdbc))return;
  LocalDate today=now.atZone(MarketCalendarService.IST).toLocalDate();
  LocalDate last;
  try{last=calendar.lastTradingDay(exchange,today);}catch(IllegalStateException ex){return;}
  // Prior completed daily turnover proxy; bounded to eight mapped stocks per exchange.
  // Do not claim this is a market-wide or order-book liquidity ranking.
  var sample=jdbc.queryForList("""
    WITH liquid AS (
      SELECT i.id,m.instrument_key,c.close*c.volume AS turnover
      FROM instruments i JOIN exchanges e ON e.id=i.exchange_id
      JOIN discovery_quote_universe m ON m.instrument_id=i.id AND m.isin=i.isin AND m.exchange=e.code
      LEFT JOIN discovery_security_context sc ON sc.instrument_id=m.instrument_id AND sc.isin=m.isin AND sc.instrument_key=m.instrument_key
      JOIN LATERAL (SELECT c.close,c.volume FROM market_candles c
        WHERE c.instrument_id=i.id AND c.timeframe='1d' AND c.is_complete
          AND c.quality_status='PROVIDER_VALIDATED'
          AND (c.candle_time AT TIME ZONE 'Asia/Kolkata')::date=?
        ORDER BY c.candle_time DESC LIMIT 1) c ON true
      WHERE e.code=? AND i.active AND i.listing_status='ACTIVE' AND i.series='EQ'
        AND i.instrument_type IN ('EQ','EQUITY','STOCK') AND c.close*c.volume>=10000000
        AND coalesce(sc.security_state,'UNKNOWN') IN ('NORMAL','UNKNOWN')
      ORDER BY turnover DESC,i.id LIMIT 8
    )
    SELECT l.id,l.instrument_key FROM liquid l LEFT JOIN intraday_research_attempts a ON a.instrument_id=l.id
    WHERE a.next_attempt_at IS NULL OR a.next_attempt_at<=now()
    ORDER BY a.attempted_at ASC NULLS FIRST,l.id LIMIT 2
    """,last,exchange);
  for(var row:sample){
   if(OperatorFeedCooldown.blocked(jdbc))return;
   long id=((Number)row.get("id")).longValue();
   int claimed=jdbc.update("""
     INSERT INTO intraday_research_attempts(instrument_id,attempted_at,next_attempt_at,status)
     VALUES (?,now(),now()+interval '5 minutes','RUNNING')
     ON CONFLICT(instrument_id) DO UPDATE SET attempted_at=now(),next_attempt_at=now()+interval '5 minutes',status='RUNNING'
     WHERE intraday_research_attempts.next_attempt_at<=now()
     """,id);
   if(claimed!=1)continue;
   try{
    int written=stocks.discoveryIntradayCandles(token,(String)row.get("instrument_key"),now);
    jdbc.update("UPDATE intraday_research_attempts SET status='SUCCESS' WHERE instrument_id=?",id);
    if(written>0)OperatorFeedCooldown.recovered(jdbc);
   }catch(Exception ex){
    jdbc.update("UPDATE intraday_research_attempts SET status='FAILED',next_attempt_at=now()+interval '15 minutes' WHERE instrument_id=?",id);
    OperatorFeedCooldown.record(jdbc,ex);
    break;
   }
  }
 }

 public Map<String,Object> current(){return current(Instant.now(),true);}
 Map<String,Object> current(Instant now,boolean includeSummary){
  List<Map<String,Object>> candidates=new ArrayList<>(),warnings=new ArrayList<>(),observations=new ArrayList<>();
  int examined=0,eligible=0;List<String> open=new ArrayList<>();
  if(permitted())for(String exchange:List.of("NSE","BSE")){
   if(!calendar.isMarketOpen(exchange,now))continue;
   open.add(exchange);
   boolean scenarioCalendar=IntradayScenario.regular(calendar.sessionContext(exchange,now),now.atZone(MarketCalendarService.IST).toLocalDate());
   // Only scheduler-collected, completed provider bars for this exact session.
   var rows=jdbc.queryForList("""
     SELECT i.id,i.symbol,i.isin,e.code AS exchange,c.candle_time,c.open,c.high,c.low,c.close,c.volume,
       coalesce(sc.security_state,'UNKNOWN') AS security_state,
       q.observed_at AS quote_observed_at,q.response_at AS quote_response_at,
       q.last_price AS quote_price,q.spread_percent AS quote_spread_percent,q.turnover_proxy AS quote_turnover
     FROM intraday_research_attempts a JOIN instruments i ON i.id=a.instrument_id
     JOIN exchanges e ON e.id=i.exchange_id JOIN market_candles c ON c.instrument_id=i.id
     JOIN data_sources ds ON ds.id=c.source_id
     JOIN discovery_quote_universe m ON m.instrument_id=i.id AND m.isin=i.isin AND m.exchange=e.code
     LEFT JOIN discovery_security_context sc ON sc.instrument_id=m.instrument_id AND sc.isin=m.isin AND sc.instrument_key=m.instrument_key
     LEFT JOIN discovery_quote_screen q ON q.instrument_id=m.instrument_id AND q.isin=m.isin AND q.instrument_key=m.instrument_key
       AND q.state IN ('PRIORITY','OBSERVED')
     WHERE e.code=? AND i.active AND i.series='EQ' AND i.listing_status='ACTIVE'
       AND a.status='SUCCESS' AND a.attempted_at>=now()-interval '15 minutes'
       AND c.timeframe='15minute' AND c.is_complete AND c.quality_status='PROVIDER_VALIDATED'
       AND ds.source_code='UPSTOX' AND c.adjustment_status='RAW_UNADJUSTED'
       AND (c.candle_time AT TIME ZONE 'Asia/Kolkata')::date=?
       AND c.candle_time+interval '15 minutes'<=?
     ORDER BY i.id,c.candle_time
     """,exchange,now.atZone(MarketCalendarService.IST).toLocalDate(),java.sql.Timestamp.from(now));
   Map<Long,List<Map<String,Object>>> groups=new LinkedHashMap<>();
   for(var row:rows)groups.computeIfAbsent(((Number)row.get("id")).longValue(),k->new ArrayList<>()).add(row);
   for(var group:groups.values()){
    examined++;
    var finding=evaluate(group,now);
    if(finding==null)continue;
    var evidence=group.getLast();
    finding.put("security_state",evidence.getOrDefault("security_state","UNKNOWN"));
    var quote=IntradayVenueEvidence.quote(evidence,now);
    if(quote!=null)finding.put("venue_quote",quote);
    observations.add(finding);
    if(IntradayVenueEvidence.restricted(finding))continue;
    if(scenarioCalendar){
     var plan=IntradayScenario.plan(finding,group,now);
     if(plan!=null)finding.put("scenario_research",plan);
    }
    eligible++;
    if("FAILED_BREAKOUT_WATCH".equals(finding.get("pattern")))warnings.add(finding);
    else if("VOLUME_BREAKOUT_WATCH".equals(finding.get("pattern")))candidates.add(finding);
   }
  }
  String status=!permitted()?"NOT_AUTHORIZED":open.isEmpty()?"SESSION_CLOSED_OR_UNVERIFIED":"RESEARCH_ONLY";
  var selection=select(candidates,warnings,status,observations,now);
  Map<String,Object> response=new LinkedHashMap<>(Map.of("status",status,"generated_at",now.toString(),"open_exchanges",open,
    "examined",examined,"eligible",eligible,"candidates",selection.get("candidates"),
    "warnings",selection.get("warnings"),"qualification",selection.get("qualification"),
    "notice","Completed 15-minute observations in a bounded sample. VWAP and volume comparisons are candle-based proxies, not live order-book liquidity. No validated trading signal, target or stop-loss."));
  if(includeSummary&&permitted())try{response.put("scenario_validation",scenarios.summary(now));}
   catch(org.springframework.dao.DataAccessException ex){response.put("scenario_validation",Map.of("status","UNAVAILABLE"));}
  return response;
 }

 static final List<String> QUALIFICATION_GAPS=List.of("LIVE_SPREAD_AND_EXECUTION_LIQUIDITY_REQUIRED",
   "VALIDATED_EXECUTION_COSTS_REQUIRED","VERIFIED_MATERIAL_EVENT_AND_RISK_ASSESSMENT_REQUIRED",
   "OFFICIAL_ASM_GSM_ESM_AND_TRADE_RESTRICTIONS_REQUIRED",
   "INTRADAY_HISTORICAL_AND_PROSPECTIVE_VALIDATION_REQUIRED","FINAL_QUALIFICATION_VALIDATION_REQUIRED");

 /** Consolidate exact public identities without transferring levels between venues.
  * Preserve the observed failed-breakout warning rather than promote a conflicting watch.
  */
 static Map<String,Object> select(List<Map<String,Object>> candidates,List<Map<String,Object>> warnings,String status){
  return select(candidates,warnings,status,List.of(),Instant.EPOCH);
 }

 static Map<String,Object> select(List<Map<String,Object>> candidates,List<Map<String,Object>> warnings,String status,
     List<Map<String,Object>> observations,Instant now){
  Map<String,List<Map<String,Object>>> byCompany=new TreeMap<>();
  int unidentified=0;
  List<Map<String,Object>> input=new ArrayList<>(candidates);input.addAll(warnings);
  for(var row:input){
   if(!(row.get("isin") instanceof String isin)||!isin.matches("INE[A-Z0-9]{9}")){
    unidentified++;continue;
   }
   byCompany.computeIfAbsent(isin,k->new ArrayList<>()).add(row);
  }
  Comparator<Map<String,Object>> order=Comparator
    .comparingDouble((Map<String,Object> row)->num(row,"relative_volume")).reversed()
    .thenComparing(row->String.valueOf(row.get("exchange")))
    .thenComparingLong(row->((Number)row.get("id")).longValue());
  List<Map<String,Object>> positive=new ArrayList<>(),negative=new ArrayList<>();
  int crossVenue=0,conflicts=0,reviewCount=0;
  Map<String,List<Map<String,Object>>> observedByCompany=new HashMap<>();
  for(var row:observations)if(row.get("isin") instanceof String isin&&isin.matches("INE[A-Z0-9]{9}"))
   observedByCompany.computeIfAbsent(isin,k->new ArrayList<>()).add(row);
  for(var entries:byCompany.values()){
   var venues=entries.stream().map(row->String.valueOf(row.get("exchange"))).distinct().sorted().toList();
   if(venues.size()>1)crossVenue++;
   var failed=entries.stream().filter(row->"FAILED_BREAKOUT_WATCH".equals(row.get("pattern"))).sorted(order).toList();
   var breakout=entries.stream().filter(row->"VOLUME_BREAKOUT_WATCH".equals(row.get("pattern"))).sorted(order).toList();
   boolean conflict=!failed.isEmpty()&&!breakout.isEmpty();
   if(conflict)conflicts++;
   if(failed.isEmpty()&&breakout.isEmpty())continue;
   // A warning always wins over a positive pattern. Venue preference cannot
   // turn a failed breakout into a positive watch or switch to a nonmatch.
   var matching=failed.isEmpty()?breakout:failed;
   var observed=observedByCompany.getOrDefault(String.valueOf(entries.getFirst().get("isin")),entries);
   var choice=IntradayVenueEvidence.choose(matching,observed,now);
   if(choice==null){conflicts++;reviewCount++;continue;}
   var representative=new LinkedHashMap<>(choice.row());
   representative.put("company_venue_context",choice.context());
   List<String> findings=new ArrayList<>();
   if(conflict)findings.add("CROSS_VENUE_FAILED_BREAKOUT_REVIEW");
   else if(!failed.isEmpty())findings.add("FAILED_BREAKOUT_REVIEW");
   findings.addAll(IntradayVenueEvidence.restrictionFindings(observed));
   if(!findings.isEmpty()){reviewCount++;representative.remove("scenario_research");}
   representative.put("stock_qualification",Map.of(
      "status",findings.isEmpty()?"WITHHELD_EVIDENCE_GAPS":"WITHHELD_REVIEW_REQUIRED",
      "horizon","INTRADAY","blockers",QUALIFICATION_GAPS,"review_findings",findings,
      "notice","Current-session technical evidence only; no execution, event or prospective validation."));
   representative.put("observed_pattern_venues",venues);
   (failed.isEmpty()?positive:negative).add(representative);
  }
  positive.sort(order);negative.sort(order);
  Map<String,Object> qualification=new LinkedHashMap<>();
  qualification.put("status",!"RESEARCH_ONLY".equals(status)?"AWAITING_RESEARCH":
       byCompany.isEmpty()?"NO_IDENTIFIED_TECHNICAL_WATCHES":"NO_QUALIFIED_IN_REVIEWED_SAMPLE");
  qualification.put("reviewed_count",byCompany.size());
  qualification.put("review_required_count",reviewCount);
  qualification.put("qualified_count","RESEARCH_ONLY".equals(status)&&!byCompany.isEmpty()?0:null);
  qualification.put("recommendations",List.of());
  qualification.put("unidentified_listing_count",unidentified);
  qualification.put("cross_venue_company_count",crossVenue);
  qualification.put("conflicting_company_count",conflicts);
  qualification.put("leading_blockers",byCompany.isEmpty()?List.of():QUALIFICATION_GAPS.stream()
    .map(code->Map.of("code",code,"count",byCompany.size())).toList());
  qualification.put("notice","Distinct exact identities among observed patterns only. Missing identity is excluded; no-pattern observations are not confirmation. No validated targets, stops or recommendations.");
  return Map.of("candidates",positive.stream().limit(5).toList(),"warnings",negative.stream().limit(5).toList(),"qualification",qualification);
 }

 static Map<String,Object> evaluate(List<Map<String,Object>> rows,Instant now){
  if(rows.size()<6||rows.size()>25)return null;
  var today=now.atZone(MarketCalendarService.IST).toLocalDate();
  Instant expected=today.atTime(9,15).atZone(MarketCalendarService.IST).toInstant();
  double sumPV=0,sumV=0,priorVolume=0,priorHigh=0,range=0,first=0;
  double close=0,high=0,volume=0,sessionLow=Double.POSITIVE_INFINITY,openingHigh=0,openingLow=Double.POSITIVE_INFINITY;
  for(int n=0;n<rows.size();n++){
   var row=rows.get(n);
   Object timestamp=row.get("candle_time");
   Instant time=timestamp instanceof java.sql.Timestamp t?t.toInstant():timestamp instanceof OffsetDateTime t?t.toInstant():timestamp instanceof Instant t?t:null;
   if(!expected.equals(time)||time.plusSeconds(900).isAfter(now))return null;
   expected=expected.plusSeconds(900);
   double o=num(row,"open"),h=num(row,"high"),l=num(row,"low"),c=num(row,"close"),v=num(row,"volume");
   if(!Double.isFinite(o+h+l+c+v)||o<=0||l<=0||c<=0||h<Math.max(o,c)||l>Math.min(o,c)||v<=0)return null;
   if(n==0)first=o;
   sessionLow=Math.min(sessionLow,l);
   if(n<2){openingHigh=Math.max(openingHigh,h);openingLow=Math.min(openingLow,l);}
   sumPV+=(h+l+c)/3*v;sumV+=v;range+=h-l;
   if(n<rows.size()-1){priorVolume+=v;priorHigh=Math.max(priorHigh,h);}
   else{close=c;high=h;volume=v;}
  }
  if(Duration.between(expected,now).toMinutes()>20)return null;
  double vwap=sumPV/sumV,rv=volume/(priorVolume/(rows.size()-1)),momentum=100*(close/first-1),rangePct=100*range/rows.size()/close;
  if(!Double.isFinite(vwap+rv+momentum+rangePct))return null;
  String pattern=high>priorHigh&&close<=priorHigh?"FAILED_BREAKOUT_WATCH":
    close>priorHigh&&close>vwap&&rv>=1.5&&momentum>0?"VOLUME_BREAKOUT_WATCH":"NO_PATTERN";
  var last=rows.getLast();
  Map<String,Object> result=new LinkedHashMap<>();
  result.put("id",last.get("id"));result.put("symbol",last.get("symbol"));result.put("exchange",last.get("exchange"));
  if(last.get("isin") instanceof String isin)result.put("isin",isin);
  result.put("pattern",pattern);result.put("bar_end",expected.toString());result.put("close",close);
  result.put("vwap_proxy",round(vwap));result.put("relative_volume",round(rv));result.put("session_change_percent",round(momentum));
  result.put("opening_range_high",openingHigh);result.put("opening_range_low",openingLow);
  result.put("session_low_so_far",sessionLow);
  result.put("price_structure_notice","Observed first 30-minute range, session low and prior high; no verified overhead target or executable stop.");
  result.put("mean_bar_range_percent",round(rangePct));result.put("prior_session_high_so_far",priorHigh);result.put("bar_count",rows.size());
  return result;
 }
 static double num(Map<String,Object> row,String key){return row.get(key) instanceof Number n?n.doubleValue():Double.NaN;}
 static double round(double n){return Math.round(n*10000)/10000d;}
}
