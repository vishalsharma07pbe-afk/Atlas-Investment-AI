package com.trading.market;
import java.time.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
class IntradayScenarioTest {
 static final LocalDate DAY=LocalDate.of(2026,11,25);
 static final Instant START=IntradayScenario.start(DAY);
 Map<String,Object> bar(int i,double o,double h,double l,double c,double v){
  return new HashMap<>(Map.of("id",1L,"isin","INE002A01018","symbol","TEST","exchange","NSE","candle_time",START.plusSeconds(i*900L),"open",o,"high",h,"low",l,"close",c,"volume",v));
 }
 List<Map<String,Object>> rows(){
  List<Map<String,Object>> rows=new ArrayList<>();
  for(int i=0;i<5;i++)rows.add(bar(i,100,102,95,100,1000));
  rows.add(bar(5,102,104,101,103,2000));
  for(int i=6;i<25;i++)rows.add(bar(i,104,105,103,104,1000));
  return rows;
 }
 @Test void freezesPrefixAndSkipsPartialBar(){
  var rows=rows();var signal=START.plusSeconds(6*900L);
  var finding=IntradayResearchService.evaluate(rows.subList(0,6),signal);
  var p=IntradayScenario.plan(finding,rows.subList(0,6),signal.plusSeconds(12));
  assertNotNull(p);assertEquals(START.plusSeconds(7*900L).toString(),p.get("entry_bar_start"));
  assertEquals("OBSERVED_CASES",IntradayScenario.outcome(p,rows,DAY).get("status"));
  rows.getFirst().put("close",101d);
  assertEquals("EVIDENCE_GAP",IntradayScenario.outcome(p,rows,DAY).get("status"));
 }
 @Test void bothBoundariesAndGapConservative(){
  var both=IntradayScenario.simulate(90,140,2,List.of(bar(7,100,145,85,110,1000)),30);
  assertEquals("AMBIGUOUS_BOTH_BOUNDARIES",both.get("status"));assertFalse(both.containsKey("net_change_percent"));
  var gap=IntradayScenario.simulate(90,140,2,List.of(bar(7,100,110,95,105,1000),bar(8,80,95,75,90,1000)),30);
  assertEquals("LOWER_GAP",gap.get("status"));assertEquals(80d,gap.get("exit_reference"));
  assertEquals("NO_ENTRY_STRESS_RATIO",IntradayScenario.simulate(90,140,2,List.of(bar(7,130,135,95,100,1000)),30).get("status"));
 }
 @Test void completeSessionReplayAndInterveningTouch(){
  var rows=rows();assertEquals("OBSERVED_CASES",IntradayScenario.replay(rows,DAY).get("status"));
  rows.get(6).put("low",101d);
  var out=IntradayScenario.replay(rows,DAY);
  for(Object c:(List<?>)out.get("cases"))assertEquals("NO_ENTRY_INTERVENING_TOUCH",((Map<?,?>)c).get("status"));
  rows.remove(20);assertEquals("EVIDENCE_GAP",IntradayScenario.replay(rows,DAY).get("status"));
 }
 @Test void lateSessionScenarioNeverCrossesClose(){
  var rows=rows();
  var signal=START.plusSeconds(21*900L);
  var prefix=rows.subList(0,21);
  var finding=new HashMap<String,Object>(Map.of("pattern","VOLUME_BREAKOUT_WATCH","bar_end",signal.toString(),"close",103d,"prior_session_high_so_far",102d,"opening_range_high",102d,"opening_range_low",95d,"mean_bar_range_percent",1d));
  assertNull(IntradayScenario.plan(finding,prefix,signal));
 }
 @Test void calendarMustBeExact(){
  assertTrue(IntradayScenario.regular(Map.of("session_date",DAY.toString(),"open_at",START.toString(),"close_at",IntradayScenario.end(DAY).toString(),"phase","POST_MARKET"),DAY));
  assertFalse(IntradayScenario.regular(Map.of("session_date",DAY.toString(),"open_at",START.toString(),"close_at",IntradayScenario.end(DAY).minusSeconds(900).toString(),"phase","POST_MARKET"),DAY));
 }
}
