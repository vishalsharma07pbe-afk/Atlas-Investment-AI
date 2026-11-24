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
