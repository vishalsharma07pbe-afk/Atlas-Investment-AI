package com.trading.market;
import java.time.*;
import java.math.BigDecimal;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class FundHistoryResearchServiceTest {
 @Test void automaticRequestsRequirePermission(){
  JdbcTemplate jdbc=mock(JdbcTemplate.class);AmfiFeedService funds=mock(AmfiFeedService.class);
  var service=new FundHistoryResearchService(jdbc,funds);service.enabled=true;service.scheduled();
  verifyNoInteractions(jdbc,funds);
 }
 @Test void heldSchemeIsCollectedBeforeDiscoveryWithoutCategoryRestriction()throws Exception{
  JdbcTemplate jdbc=mock(JdbcTemplate.class);AmfiFeedService funds=mock(AmfiFeedService.class);
  var service=new FundHistoryResearchService(jdbc,funds);service.enabled=true;service.permitted=true;
  when(jdbc.queryForList(contains("FROM personal_holdings h"),any(LocalDate.class),any(LocalDate.class)))
    .thenReturn(List.of(Map.of("scheme_code",123456L),Map.of("scheme_code",234567L)));
  when(jdbc.update(contains("INSERT INTO fund_history_attempts"),eq(123456L))).thenReturn(1);
  when(funds.history(123456L)).thenReturn(800);
  service.scheduled();
  verify(funds).history(123456L);
  verify(funds,never()).history(234567L);
  verify(jdbc).update(contains("SET status=?"),eq("SUCCESS"),eq(123456L));
  var ordered=inOrder(jdbc,funds);
  ordered.verify(funds).history(123456L);
  ordered.verify(jdbc,times(6)).queryForList(contains("lower(trim(s.category))"),anyString(),
    any(LocalDate.class),any(LocalDate.class));
 }
 @Test void heldSchemeFailureKeepsExistingRetryLedger()throws Exception{
  JdbcTemplate jdbc=mock(JdbcTemplate.class);AmfiFeedService funds=mock(AmfiFeedService.class);
  var service=new FundHistoryResearchService(jdbc,funds);service.enabled=true;service.permitted=true;
  when(jdbc.queryForList(contains("FROM personal_holdings h"),any(LocalDate.class),any(LocalDate.class)))
    .thenReturn(List.of(Map.of("scheme_code",123456L)));
  when(jdbc.update(contains("INSERT INTO fund_history_attempts"),eq(123456L))).thenReturn(1);
  when(funds.history(123456L)).thenThrow(new IllegalStateException("source unavailable"));
  service.scheduled();
  verify(jdbc).update(contains("SET status='FAILED'"),eq(123456L));
 }
 @Test void sampledHistoriesUsesOneBoundedQueryAndKeepsSchemesSeparate(){
  JdbcTemplate jdbc=mock(JdbcTemplate.class);
  var service=new FundHistoryResearchService(jdbc,mock(AmfiFeedService.class));
  LocalDate today=LocalDate.of(2026,11,24);
  var first=Map.<String,Object>of("scheme_code",123L,"nav_date",today.minusDays(1),"nav",BigDecimal.TEN,"source_code","AMFI");
  var second=Map.<String,Object>of("scheme_code",123L,"nav_date",today,"nav",BigDecimal.ONE,"source_code","AMFI");
  var other=Map.<String,Object>of("scheme_code",456L,"nav_date",today,"nav",BigDecimal.TEN,"source_code","AMFI");
  when(jdbc.queryForList(contains("scheme_code IN (?,?)"),eq(123L),eq(456L),eq(today),eq(today)))
   .thenReturn(List.of(first,second,other));
  assertTrue(service.sampledHistories(List.of(),today).isEmpty());
  verifyNoInteractions(jdbc);
  var result=service.sampledHistories(List.of(Map.of("scheme_code",123L),Map.of("scheme_code",456L)),today);
  assertEquals(List.of(first,second),result.get(123L));
  assertEquals(List.of(other),result.get(456L));
  verify(jdbc,times(1)).queryForList(contains("scheme_code IN (?,?)"),eq(123L),eq(456L),eq(today),eq(today));
  assertThrows(IllegalArgumentException.class,()->service.sampledHistories(Collections.nCopies(41,Map.of("scheme_code",123L)),today));
 }
 @Test void datedHistoryWithAmfiAnchorProducesObservedReturns(){
  LocalDate end=LocalDate.of(2026,11,24);
  List<Map<String,Object>> rows=new ArrayList<>();
  for(int i=0;i<=1100;i++)rows.add(Map.of("nav_date",end.minusDays(1100-i),"nav",BigDecimal.valueOf(100+i*.01),"source_code",i==1100?"AMFI":"MFAPI"));
  var result=FundHistoryResearchService.metrics(rows,end);
  assertNotNull(result);assertEquals(0.0,result.get("drawdown_3y_percent"));
  assertTrue((Double)result.get("cagr_3y_percent")>0);
  assertNull(FundHistoryResearchService.metrics(rows,end.plusDays(8)));
  assertNull(FundHistoryResearchService.metrics(rows.subList(0,100),end));
 }

 @Test void newerSecondaryNavNeverDisplacesRecentOfficialAnchor(){
  LocalDate end=LocalDate.of(2026,11,23),today=end.plusDays(2);
  List<Map<String,Object>> rows=new ArrayList<>();
  for(int i=0;i<=1100;i++)rows.add(Map.of("nav_date",end.minusDays(1100-i),"nav",BigDecimal.valueOf(100+i*.01),"source_code",i==1100?"AMFI":"MFAPI"));
  var expected=FundHistoryResearchService.metrics(rows,today);
  assertNotNull(expected);
  rows.add(Map.of("nav_date",end.plusDays(1),"nav",BigDecimal.valueOf(900),"source_code","MFAPI"));
  rows.add(Map.of("nav_date",today,"nav",BigDecimal.ONE,"source_code","MFAPI"));
  assertEquals(expected,FundHistoryResearchService.metrics(rows,today));
  assertEquals(end.toString(),expected.get("nav_date"));
  assertEquals(111.0,expected.get("nav"));
  assertNull(FundHistoryResearchService.metrics(rows,end.plusDays(8)));
  var noOfficial=rows.stream().map(row->Map.<String,Object>of("nav_date",row.get("nav_date"),"nav",row.get("nav"),"source_code","MFAPI")).toList();
  assertNull(FundHistoryResearchService.metrics(noOfficial,today));
  var gap=new ArrayList<>(rows);
  gap.subList(700,730).clear();
  assertNull(FundHistoryResearchService.metrics(gap,today));
  rows.add(Map.of("nav_date",today,"nav",BigDecimal.TEN,"source_code","MFAPI"));
  assertNull(FundHistoryResearchService.metrics(rows,today));
 }
 @Test void downsideRiskAndRollingRangeUseObservedWeeklyAnchors(){
  LocalDate end=LocalDate.of(2026,11,24);
  List<Map<String,Object>> rows=new ArrayList<>();
  for(int i=0;i<=156;i++)rows.add(Map.of("nav_date",end.minusWeeks(156-i),"nav",BigDecimal.valueOf(i%2==0?100:90)));
  var risk=FundHistoryResearchService.weeklyRisk(rows,end);
  assertEquals(50.0,risk.get("negative_week_percent"));
  assertEquals(50.9902,(Double)risk.get("weekly_downside_deviation_percent"),0.0001);
  assertEquals(0.0,risk.get("median_rolling_52w_annualized_percent"));
  assertEquals(0.0,risk.get("best_rolling_52w_annualized_percent"));
 }
 @Test void hurdleSensitivityUsesArithmeticExcessSampleVarianceAndAllDownsideIntervals(){
  var returns=new ArrayList<Double>();
  for(int i=0;i<156;i++)returns.add(i%2==0?-.01:.02);
  var block=FundHistoryResearchService.weeklyHurdleSensitivity(returns);
  assertEquals("HYPOTHETICAL_HURDLE_ONLY",block.get("status"));
  assertEquals(26.0,block.get("annualized_arithmetic_return_percent"));
  double vol=100*Math.sqrt(52*156*.015*.015/155);
  assertEquals(vol,(Double)block.get("annualized_volatility_percent"),.0001);
  var scenarios=(List<?>)block.get("scenarios");
  var zero=(Map<?,?>)scenarios.getFirst();var six=(Map<?,?>)scenarios.getLast();
  assertEquals(26/vol,(Double)zero.get("sharpe_proxy"),.0001);
  assertEquals(26/(100*Math.sqrt(52*.0001/2)),(Double)zero.get("sortino_proxy"),.0001);
  double hurdle=Math.expm1(Math.log1p(.06)/52);
  double excess=100*52*(.005-hurdle);
  assertEquals(excess,(Double)six.get("annualized_arithmetic_excess_percent"),.0001);
  assertEquals(excess/(100*Math.sqrt(52*Math.pow(-.01-hurdle,2)/2)),(Double)six.get("sortino_proxy"),.0001);
 }
 @Test void hurdleSensitivityRejectsIncompleteInvalidAndNearZeroDenominators(){
  assertTrue(FundHistoryResearchService.weeklyHurdleSensitivity(Collections.nCopies(155,.01)).isEmpty());
  assertTrue(FundHistoryResearchService.weeklyHurdleSensitivity(Collections.nCopies(156,Double.NaN)).isEmpty());
  var flat=FundHistoryResearchService.weeklyHurdleSensitivity(Collections.nCopies(156,0.0));
  var zero=(Map<?,?>)((List<?>)flat.get("scenarios")).getFirst();
  var six=(Map<?,?>)((List<?>)flat.get("scenarios")).getLast();
  assertNull(zero.get("sharpe_proxy"));assertNull(zero.get("sortino_proxy"));
  assertNull(six.get("sharpe_proxy"));assertEquals(-Math.sqrt(52),(Double)six.get("sortino_proxy"),.0001);
 }
 @Test void capitalPreservationUsesOverlappingNonAnnualizedHoldingPeriods(){
  var anchors=new ArrayList<Double>();
  for(int i=0;i<=156;i++)anchors.add(i%2==0?100.0:90.0);
  var block=FundHistoryResearchService.capitalPreservation(anchors);
  assertEquals("HISTORICAL_NAV_WINDOWS_ONLY",block.get("status"));
  var windows=(List<?>)block.get("windows");
  var four=(Map<?,?>)windows.get(0);var thirteen=(Map<?,?>)windows.get(1);var twentySix=(Map<?,?>)windows.get(2);
  assertEquals(153,four.get("window_count"));assertEquals(153,four.get("flat_windows"));
  assertEquals(144,thirteen.get("window_count"));assertEquals(72,thirteen.get("loss_windows"));
  assertEquals(72,thirteen.get("gain_windows"));assertEquals(50.0,thirteen.get("loss_window_percent"));
  assertEquals(-10.0,thirteen.get("worst_return_percent"));assertEquals(-10.0,thirteen.get("fifth_percentile_return_percent"));
  assertEquals(11.1111,thirteen.get("best_return_percent"));assertEquals(131,twentySix.get("flat_windows"));
  assertTrue(FundHistoryResearchService.capitalPreservation(anchors.subList(0,156)).isEmpty());
  anchors.set(0,Double.NaN);assertTrue(FundHistoryResearchService.capitalPreservation(anchors).isEmpty());
 }
 @Test void underwaterDurationIncludesUnrecoveredObservedDecline(){
  LocalDate end=LocalDate.of(2026,11,24);
  List<Map<String,Object>> rows=new ArrayList<>();
  for(int i=0;i<=1100;i++){
    double nav=i<1090?100:90;
    rows.add(Map.of("nav_date",end.minusDays(1100-i),"nav",BigDecimal.valueOf(nav),"source_code",i==1100?"AMFI":"MFAPI"));
  }
  var result=FundHistoryResearchService.metrics(rows,end);
  assertNotNull(result);
  assertEquals(11L,result.get("current_observed_underwater_days"));
  assertEquals(11L,result.get("longest_observed_underwater_days"));
 }
 @Test void rollingPeerConsistencyRequiresExactDistinctDirectGrowthAndMatchedDates(){
  LocalDate end=LocalDate.of(2026,11,24);
  List<Map<String,Object>> funds=new ArrayList<>();
  Map<Long,List<Map<String,Object>>> histories=new HashMap<>();
  for(long id=1;id<=5;id++){
    Map<String,Object> row=new HashMap<>(Map.of("scheme_code",id,"amfi_plan","DIRECT","amfi_option","GROWTH",
      "isin_growth","INF"+String.format("%09d",id),"amfi_metadata_date",end,"nav_date",end.toString()));
    funds.add(row);
    List<Map<String,Object>> points=new ArrayList<>();
    for(int i=0;i<=156;i++)points.add(Map.of("nav_date",end.minusWeeks(156-i),"nav",BigDecimal.valueOf(100+i*id)));
    histories.put(id,points);
  }
  FundHistoryResearchService.rollingPeerConsistency(funds,histories,end);
  var highest=(Map<?,?>)funds.getLast().get("rolling_peer_consistency");
  assertNotNull(highest);assertEquals(105,highest.get("matched_windows"));assertEquals(4,highest.get("minimum_peer_count"));
  assertEquals(100.0,highest.get("above_median_percent"));
  var lowest=(Map<?,?>)funds.getFirst().get("rolling_peer_consistency");
  assertEquals(0.0,lowest.get("above_median_percent"));
  for(var row:funds)row.remove("rolling_peer_consistency");
  // A one-day offset is permissible for weekly NAV proxies, but not an exact peer endpoint.
  histories.put(1L,histories.get(1L).stream().map(p->Map.<String,Object>of("nav_date",((LocalDate)p.get("nav_date")).minusDays(1),"nav",p.get("nav"))).toList());
  FundHistoryResearchService.rollingPeerConsistency(funds,histories,end);
  assertTrue(funds.stream().noneMatch(row->row.containsKey("rolling_peer_consistency")));
  funds.getFirst().put("isin_growth",funds.getLast().get("isin_growth"));
  FundHistoryResearchService.rollingPeerConsistency(funds,histories,end);
  assertTrue(funds.stream().noneMatch(row->row.containsKey("rolling_peer_consistency")));
 }
 @Test void weeklyRiskUsesBoundedAnchorsAndRejectsMissingWeeks(){
  LocalDate end=LocalDate.of(2026,11,24);
  List<Map<String,Object>> rows=new ArrayList<>();
  for(int i=156;i>=0;i--)rows.add(Map.of("nav_date",end.minusWeeks(i),"nav",BigDecimal.valueOf(100+(156-i)*.2)));
  var risk=FundHistoryResearchService.weeklyRisk(rows,end);
  assertEquals(156,risk.get("weekly_intervals"));
  var matched=(Map<?,?>)risk.get("matched_weekly_comparison");
  assertNotNull(matched);assertEquals(157,matched.get("anchor_count"));
  assertEquals(end.toString(),matched.get("last_date"));
  assertEquals(0.0,matched.get("drawdown_percent"));
  var shifted=new ArrayList<>(rows);
  var changed=new HashMap<>(shifted.get(50));changed.put("nav_date",((LocalDate)changed.get("nav_date")).minusDays(1));shifted.set(50,changed);
  var alternate=(Map<?,?>)FundHistoryResearchService.weeklyRisk(shifted,end).get("matched_weekly_comparison");
  assertNotNull(alternate);assertNotEquals(matched.get("date_digest"),alternate.get("date_digest"));
  assertNotNull(risk.get("weekly_hurdle_sensitivity"));
  assertEquals(105,risk.get("rolling_windows"));
  assertEquals(100.0,risk.get("positive_rolling_52w_percent"));
  assertTrue((Double)risk.get("weekly_volatility_percent")>=0);
  rows.remove(50);assertTrue(FundHistoryResearchService.weeklyRisk(rows,end).isEmpty());
 }
}
