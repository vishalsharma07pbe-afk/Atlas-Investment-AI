package com.trading.market;

import java.time.*;
import java.util.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.core.type.TypeReference;
import org.springframework.jdbc.core.JdbcTemplate;

/** Local-only scheduler-owned evidence; GET never publishes or fetches provider data. */
final class IntradayScenarioLedger {
 private final JdbcTemplate jdbc;
 private final MarketCalendarService calendar;
 private final ObjectMapper json=new ObjectMapper();
 IntradayScenarioLedger(JdbcTemplate jdbc,MarketCalendarService calendar){this.jdbc=jdbc;this.calendar=calendar;}
 private String encode(Map<String,Object> value){try{return json.writeValueAsString(value);}catch(Exception ex){throw new IllegalStateException("scenario serialization",ex);}}
 private Map<String,Object> decode(Object value){try{return json.readValue(String.valueOf(value),new TypeReference<Map<String,Object>>(){});}catch(Exception ex){return Map.of();}}
 private static final String NOTICE=IntradayScenario.NOTICE+" Retrospective sample is current active registry, cached full sessions only, not point-in-time selection. Prospective outcomes retain missing observations; no independent calibration.";
 List<Map<String,Object>> bars(long id,String isin,String exchange,String symbol,LocalDate day,Instant through){
  return jdbc.queryForList("""
   SELECT c.candle_time,c.open,c.high,c.low,c.close,c.volume,i.id,i.isin,i.symbol,e.code AS exchange
   FROM market_candles c JOIN instruments i ON i.id=c.instrument_id JOIN exchanges e ON e.id=i.exchange_id
   JOIN data_sources ds ON ds.id=c.source_id
   WHERE i.id=? AND i.isin=? AND e.code=? AND i.symbol=? AND i.active AND i.series='EQ' AND i.listing_status='ACTIVE'
    AND c.timeframe='15minute' AND c.is_complete AND c.quality_status='PROVIDER_VALIDATED'
    AND c.adjustment_status='RAW_UNADJUSTED' AND ds.source_code='UPSTOX'
    AND c.candle_time>=? AND c.candle_time<? AND c.candle_time+interval '15 minutes'<=?
   ORDER BY c.candle_time LIMIT 26
   """,id,isin,exchange,symbol,java.sql.Timestamp.from(IntradayScenario.start(day)),java.sql.Timestamp.from(IntradayScenario.end(day)),java.sql.Timestamp.from(through));
 }
 void publish(Map<String,Object> snapshot,Instant now){
  if(!"RESEARCH_ONLY".equals(snapshot.get("status"))||!(snapshot.get("candidates") instanceof List<?> list))return;
  LocalDate day=now.atZone(MarketCalendarService.IST).toLocalDate();
  for(Object v:list){
   if(!(v instanceof Map<?,?> row)||!(row.get("scenario_research") instanceof Map<?,?> raw)||
      !(row.get("stock_qualification") instanceof Map<?,?> q)||!(q.get("review_findings") instanceof List<?> findings)||!findings.isEmpty())continue;
   if(!(row.get("isin") instanceof String isin)||!isin.matches("INE[A-Z0-9]{9}")||!(row.get("id") instanceof Number id))continue;
   String exchange=String.valueOf(row.get("exchange")),symbol=String.valueOf(row.get("symbol"));
   if(!IntradayScenario.regular(calendar.sessionContext(exchange,now),day))continue;
   // Re-read original prefix at publication and recompute to reject a
   // revision or elapsed bar between observation and the scheduler write.
   var signal=IntradayVenueEvidence.instant(row.get("bar_end"));
   if(signal==null)continue;
   var prefix=bars(id.longValue(),isin,exchange,symbol,day,signal);
   var fresh=IntradayResearchService.evaluate(prefix,now);
   if(fresh==null)continue;
   var p=IntradayScenario.plan(fresh,prefix,now);
   if(p==null||!Objects.equals(raw.get("prefix_sha256"),p.get("prefix_sha256")))continue;
   // Publication must not use a stale/unknown quote as evidence of execution.
   // Quote is only contextual; never a fill or independent clearance.
   jdbc.update("""
    INSERT INTO intraday_scenario_watch(session_date,isin,instrument_id,exchange,symbol,published_at,expiry,evidence)
    VALUES (?,?,?,?,?,?,?,CAST(? AS jsonb)) ON CONFLICT(session_date,isin) DO NOTHING
    """,day,isin,id.longValue(),exchange,symbol,java.sql.Timestamp.from(now),
      java.sql.Timestamp.from(Instant.parse((String)p.get("expiry"))),encode(p));
  }
 }
 void settle(Instant now){
  var pending=jdbc.queryForList("""
   SELECT * FROM intraday_scenario_watch WHERE status='PENDING' AND expiry+interval '5 minutes'<=?
   ORDER BY expiry,instrument_id LIMIT 20
   """,java.sql.Timestamp.from(now));
  for(var row:pending){
   LocalDate day=LocalDate.parse(String.valueOf(row.get("session_date")));
   String exchange=String.valueOf(row.get("exchange")),isin=String.valueOf(row.get("isin")),symbol=String.valueOf(row.get("symbol"));
   long id=((Number)row.get("instrument_id")).longValue();
   var p=decode(row.get("evidence"));
   var expiry=IntradayVenueEvidence.instant(row.get("expiry"));
   if(expiry==null)continue;
   var context=calendar.sessionContext(exchange,IntradayScenario.end(day));
   var result=IntradayScenario.regular(context,day)?IntradayScenario.outcome(p,bars(id,isin,exchange,symbol,day,expiry),day):IntradayScenario.gap();
   String status=String.valueOf(result.get("status"));
   // Allow later same-session ingestion, but finalize missing evidence
   // after a bounded grace period; never silently drop unresolved watches.
   if("EVIDENCE_GAP".equals(status)&&now.isBefore(IntradayScenario.end(day).plusSeconds(3600)))continue;
   jdbc.update("""
     UPDATE intraday_scenario_watch SET status=?,outcome=CAST(? AS jsonb)
     WHERE session_date=? AND isin=? AND status='PENDING'
     """,status,encode(result),day,isin);
  }
 }
 void replayOne(Instant now){
  LocalDate today=now.atZone(MarketCalendarService.IST).toLocalDate();
  // One bounded cached complete-session sample per pass, independent of
  // current watch score. No historical provider backfill in this worker.
  var due=jdbc.queryForList("""
    WITH sessions AS (
     SELECT c.instrument_id,(c.candle_time AT TIME ZONE 'Asia/Kolkata')::date AS day
     FROM market_candles c JOIN data_sources ds ON ds.id=c.source_id
     WHERE c.timeframe='15minute' AND c.is_complete AND c.quality_status='PROVIDER_VALIDATED'
       AND c.adjustment_status='RAW_UNADJUSTED' AND ds.source_code='UPSTOX'
       AND c.candle_time>=? AND c.candle_time<?
     GROUP BY c.instrument_id,(c.candle_time AT TIME ZONE 'Asia/Kolkata')::date HAVING count(*)=25
    )
    SELECT i.id,i.isin,i.symbol,e.code AS exchange,s.day FROM sessions s
    JOIN instruments i ON i.id=s.instrument_id JOIN exchanges e ON e.id=i.exchange_id
    WHERE i.active AND i.series='EQ' AND i.listing_status='ACTIVE' AND i.isin ~ '^INE[A-Z0-9]{9}$'
      AND e.code IN ('NSE','BSE') AND NOT EXISTS (SELECT 1 FROM intraday_scenario_replay r WHERE r.instrument_id=i.id AND r.session_date=s.day)
    ORDER BY s.day,i.id LIMIT 1
    """,java.sql.Timestamp.from(IntradayScenario.start(today.minusDays(30))),java.sql.Timestamp.from(IntradayScenario.start(today)));
  for(var r:due){
   LocalDate day=LocalDate.parse(String.valueOf(r.get("day")));long id=((Number)r.get("id")).longValue();
   String isin=String.valueOf(r.get("isin")),exchange=String.valueOf(r.get("exchange")),symbol=String.valueOf(r.get("symbol"));
   var result=IntradayScenario.regular(calendar.sessionContext(exchange,IntradayScenario.end(day)),day)?
      IntradayScenario.replay(bars(id,isin,exchange,symbol,day,IntradayScenario.end(day)),day):IntradayScenario.gap();
   jdbc.update("""
     INSERT INTO intraday_scenario_replay VALUES (?,?,?,?,?,CAST(? AS jsonb)) ON CONFLICT DO NOTHING
     """,day,id,isin,exchange,java.sql.Timestamp.from(now),encode(result));
  }
 }
 Map<String,Object> summary(Instant now){
  LocalDate day=now.atZone(MarketCalendarService.IST).toLocalDate();
  var live=jdbc.queryForList("SELECT status,outcome FROM intraday_scenario_watch WHERE session_date>=? AND session_date<=? ORDER BY session_date,isin LIMIT 1001",day.minusDays(30),day);
  var history=jdbc.queryForList("SELECT outcome FROM intraday_scenario_replay WHERE session_date>=? AND session_date<? ORDER BY session_date,instrument_id LIMIT 1001",day.minusDays(30),day);
  return Map.of("methodology",IntradayScenario.VERSION,"prospective",summarize(live,true),"historical",summarize(history,false),"notice",NOTICE);
 }
 Map<String,Object> summarize(List<Map<String,Object>> rows,boolean prospective){
  Map<String,Integer> statuses=new TreeMap<>();
  Map<Integer,List<Map<String,Object>>> cases=new LinkedHashMap<>();
  for(int bps:IntradayScenario.COSTS)cases.put(bps,new ArrayList<>());
  int pending=0;
  for(var row:rows.stream().limit(1000).toList()){
   var r=decode(row.get("outcome"));String status=prospective?String.valueOf(row.get("status")):String.valueOf(r.getOrDefault("status","EVIDENCE_GAP"));
   statuses.merge(status,1,Integer::sum);if("PENDING".equals(status))pending++;
   if(!"OBSERVED_CASES".equals(status)||!(r.get("cases") instanceof List<?> list))continue;
   for(var x:list)if(x instanceof Map<?,?> c&&c.get("cost_bps_per_side") instanceof Number n&&cases.containsKey(n.intValue())){
    Map<String,Object> copy=new HashMap<>();c.forEach((k,v)->{if(k instanceof String s)copy.put(s,v);});cases.get(n.intValue()).add(copy);
   }
  }
  List<Map<String,Object>> results=new ArrayList<>();
  for(var entry:cases.entrySet()){
   Map<String,Integer> counts=new TreeMap<>();List<Double> returns=new ArrayList<>();
   for(var c:entry.getValue()){
    counts.merge(String.valueOf(c.get("status")),1,Integer::sum);
    if(c.get("net_change_percent") instanceof Number n&&Double.isFinite(n.doubleValue()))returns.add(n.doubleValue());
   }
   Map<String,Object> result=new LinkedHashMap<>();
   result.put("cost_bps_per_side",entry.getKey());result.put("counts",counts);result.put("observed_cases",entry.getValue().size());
   result.put("resolved_returns",returns.size());result.put("mean_net_change_percent",returns.isEmpty()?null:returns.stream().mapToDouble(x->x).average().orElseThrow());
   result.put("worst_net_change_percent",returns.isEmpty()?null:Collections.min(returns));results.add(result);
  }
  return Map.of("sample_count",Math.min(rows.size(),1000),"pending_count",pending,"statuses",statuses,"cost_scenarios",results,"truncated",rows.size()>1000,"calibrated",false);
 }
}
