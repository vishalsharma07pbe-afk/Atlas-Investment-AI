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
  when(jdbc.queryForList(contains("FROM personal_holdings h"),any(LocalDate.class),any(LocalDate.class),
    any(LocalDate.class),any(LocalDate.class),any(LocalDate.class),any(LocalDate.class)))
    .thenReturn(List.of(Map.of("scheme_code",123456L),Map.of("scheme_code",234567L)));
  when(jdbc.update(contains("INSERT INTO fund_history_attempts"),eq(123456L))).thenReturn(1);
  when(funds.history(123456L)).thenReturn(800);
  service.scheduled();
  verify(funds).history(123456L);
  verify(funds,never()).history(234567L);
  verify(jdbc).update(contains("SET status=?"),eq("SUCCESS"),eq(123456L));
  var ordered=inOrder(jdbc,funds);
  ordered.verify(funds).history(123456L);
  ordered.verify(jdbc,times(5)).queryForList(contains("lower(trim(s.category))"),anyString(),
    any(LocalDate.class),any(LocalDate.class),any(LocalDate.class),any(LocalDate.class));
 }
 @Test void heldSchemeFailureKeepsExistingRetryLedger()throws Exception{
  JdbcTemplate jdbc=mock(JdbcTemplate.class);AmfiFeedService funds=mock(AmfiFeedService.class);
  var service=new FundHistoryResearchService(jdbc,funds);service.enabled=true;service.permitted=true;
  when(jdbc.queryForList(contains("FROM personal_holdings h"),any(LocalDate.class),any(LocalDate.class),
    any(LocalDate.class),any(LocalDate.class),any(LocalDate.class),any(LocalDate.class)))
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
 @Test void weeklyRiskUsesBoundedAnchorsAndRejectsMissingWeeks(){
  LocalDate end=LocalDate.of(2026,11,24);
  List<Map<String,Object>> rows=new ArrayList<>();
  for(int i=156;i>=0;i--)rows.add(Map.of("nav_date",end.minusWeeks(i),"nav",BigDecimal.valueOf(100+(156-i)*.2)));
  var risk=FundHistoryResearchService.weeklyRisk(rows,end);
  assertEquals(156,risk.get("weekly_intervals"));
  assertEquals(105,risk.get("rolling_windows"));
  assertEquals(100.0,risk.get("positive_rolling_52w_percent"));
  assertTrue((Double)risk.get("weekly_volatility_percent")>=0);
  rows.remove(50);assertTrue(FundHistoryResearchService.weeklyRisk(rows,end).isEmpty());
 }
}
