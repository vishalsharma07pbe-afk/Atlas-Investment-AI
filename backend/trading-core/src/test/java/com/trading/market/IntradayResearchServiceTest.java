package com.trading.market;
import java.time.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class IntradayResearchServiceTest {
 static final Instant START=LocalDate.of(2026,11,25).atTime(9,15).atZone(MarketCalendarService.IST).toInstant();
 List<Map<String,Object>> bars(double lastClose,double lastHigh){
  List<Map<String,Object>> rows=new ArrayList<>();
  for(int n=0;n<6;n++)rows.add(new HashMap<>(Map.of("id",1L,"symbol","TEST","exchange","NSE","candle_time",START.plusSeconds(n*900L),"open",100d,"high",n==5?lastHigh:101d,"low",99d,"close",n==5?lastClose:100d,"volume",n==5?2000L:1000L)));
  return rows;
 }
 @Test void gatesIncompleteStaleAndMissingBars(){
  var rows=bars(102,103);
  assertNull(IntradayResearchService.evaluate(rows,START.plusSeconds(5*900L)));
  assertNull(IntradayResearchService.evaluate(rows,START.plusSeconds(8*900L)));
  rows.remove(2);assertNull(IntradayResearchService.evaluate(rows,START.plusSeconds(6*900L)));
 }
 @Test void separatesBreakoutAndFailedBreakout(){
  var now=START.plusSeconds(6*900L);
  assertEquals("VOLUME_BREAKOUT_WATCH",IntradayResearchService.evaluate(bars(102,103),now).get("pattern"));
  assertEquals("FAILED_BREAKOUT_WATCH",IntradayResearchService.evaluate(bars(100,103),now).get("pattern"));
 }
 @Test void openingRangeAndSessionReferencesUseCompletedBars(){
  var result=IntradayResearchService.evaluate(bars(102,103),START.plusSeconds(6*900L));
  assertEquals(101d,result.get("opening_range_high"));
  assertEquals(99d,result.get("opening_range_low"));
  assertEquals(99d,result.get("session_low_so_far"));
  assertEquals(101d,result.get("prior_session_high_so_far"));
 }
 @Test void exactCompanySelectionPreservesCrossVenueFailedBreakout(){
  var now=START.plusSeconds(6*900L);
  var n=IntradayResearchService.evaluate(bars(102,103),now);
  n.put("isin","INE002A01018");
  var b=IntradayResearchService.evaluate(bars(100,103),now);
  b.put("isin","INE002A01018");b.put("exchange","BSE");b.put("id",2L);
  var unknown=IntradayResearchService.evaluate(bars(102,103),now);
  var selected=IntradayResearchService.select(List.of(n,unknown),List.of(b),"RESEARCH_ONLY");
  assertEquals(List.of(),selected.get("candidates"));
  var warnings=(List<?>)selected.get("warnings");
  assertEquals(1,warnings.size());
  var chosen=(Map<?,?>)warnings.getFirst();
  assertEquals("BSE",chosen.get("exchange"));assertEquals(100d,chosen.get("close"));
  var q=(Map<?,?>)selected.get("qualification");
  assertEquals(1,q.get("reviewed_count"));assertEquals(1,q.get("conflicting_company_count"));
  assertEquals(1,q.get("unidentified_listing_count"));assertEquals(0,q.get("qualified_count"));
  assertEquals(List.of(),q.get("recommendations"));
  assertNull(((Map<?,?>)IntradayResearchService.select(List.of(),List.of(),"SESSION_CLOSED_OR_UNVERIFIED").get("qualification")).get("qualified_count"));
 }
 @Test void pairedQuotesChooseOnlySamePatternAndPreserveVenueLevels(){
  var now=START.plusSeconds(6*900L);
  var n=IntradayResearchService.evaluate(bars(102,103),now);
  var b=IntradayResearchService.evaluate(bars(103,104),now);
  n.put("isin","INE002A01018");b.put("isin","INE002A01018");
  b.put("exchange","BSE");b.put("id",2L);
  n.put("venue_quote",quote(now,.3,20));b.put("venue_quote",quote(now,.1,25));
  var selected=IntradayResearchService.select(List.of(n,b),List.of(),"RESEARCH_ONLY",List.of(n,b),now);
  var chosen=(Map<?,?>)((List<?>)selected.get("candidates")).getFirst();
  assertEquals("BSE",chosen.get("exchange"));assertEquals(103d,chosen.get("close"));
  var context=(Map<?,?>)chosen.get("company_venue_context");
  assertEquals("PAIRED_QUOTE_LIQUIDITY_PREFERENCE",context.get("status"));assertEquals(false,context.get("execution_verified"));
  b.put("venue_quote",quote(now.minusSeconds(1000),.1,25));
  selected=IntradayResearchService.select(List.of(n,b),List.of(),"RESEARCH_ONLY",List.of(n,b),now);
  chosen=(Map<?,?>)((List<?>)selected.get("candidates")).getFirst();
  assertNull(((Map<?,?>)chosen.get("company_venue_context")).get("preferred_exchange"));
  b.put("venue_quote",quote(now,.1,25));b.put("pattern","FAILED_BREAKOUT_WATCH");
  selected=IntradayResearchService.select(List.of(n),List.of(b),"RESEARCH_ONLY",List.of(n,b),now);
  assertEquals(List.of(),selected.get("candidates"));
  assertEquals("BSE",((Map<?,?>)((List<?>)selected.get("warnings")).getFirst()).get("exchange"));
 }
 @Test void restrictedAlternativeAndConflictingIdentityNeverPromote(){
  var now=START.plusSeconds(6*900L);
  var n=IntradayResearchService.evaluate(bars(102,103),now);
  n.put("isin","INE002A01018");
  var b=new HashMap<>(n);b.put("exchange","BSE");b.put("id",2L);b.put("security_state","SUSPENDED_REPORTED");
  var selected=IntradayResearchService.select(List.of(n,b),List.of(),"RESEARCH_ONLY",List.of(n,b),now);
  var chosen=(Map<?,?>)((List<?>)selected.get("candidates")).getFirst();
  assertEquals("NSE",chosen.get("exchange"));
  assertTrue(((List<?>)((Map<?,?>)chosen.get("stock_qualification")).get("review_findings")).contains("REPORTED_SUSPENDED_REPORTED_AT_BSE"));
  var duplicate=new HashMap<>(n);duplicate.put("id",3L);
  selected=IntradayResearchService.select(List.of(n,b),List.of(),"RESEARCH_ONLY",List.of(n,b,duplicate),now);
  assertEquals(List.of(),selected.get("candidates"));
 }
 static Map<String,Object> quote(Instant now,double spread,double turnover){
  return Map.of("observed_at",now.minusSeconds(20).toString(),"response_at",now.minusSeconds(10).toString(),
      "price",100d,"spread_percent",spread,"turnover_proxy_cr",turnover);
 }
 @Test void neverRequestsWithoutEntitlement(){
  var jdbc=mock(JdbcTemplate.class);var stocks=mock(UpstoxFeedService.class);var calendar=mock(MarketCalendarService.class);
  var service=new IntradayResearchService(jdbc,stocks,calendar);
  service.enabled=true;service.rights=true;service.token="test-only";
  service.scheduled();verifyNoInteractions(jdbc,stocks,calendar);
 }
}
