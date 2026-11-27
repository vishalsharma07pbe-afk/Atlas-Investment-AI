package com.trading.market;

import java.time.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;

class DiscoveryHistorySchedulerTest {
  @Test void prioritizesOverdueExistingHistoriesWithSeparateExpansionBudget(){
    JdbcTemplate db=mock(JdbcTemplate.class);
    DiscoveryHistoryScheduler scheduler=new DiscoveryHistoryScheduler(db,mock(UpstoxFeedService.class),mock(MarketCalendarService.class));
    LocalDate end=LocalDate.of(2026,11,26);
    scheduler.refreshExchange("NSE",end);
    verify(db).queryForList(argThat(sql->sql.contains("h.candle_count>=25 AND h.latest_date<?")&&sql.contains("workload=0 AND position<=8")&&sql.contains("workload=1 AND position<=2")&&sql.contains("ORDER BY workload,position LIMIT 10")),eq("NSE"),eq(end.minusMonths(15)),eq(end),eq(end),eq(end.minusMonths(15)),eq(end),eq(end),eq("NSE"),eq(253),eq(end));
  }

  @Test void requiresAllPermissionGates(){
    JdbcTemplate db=mock(JdbcTemplate.class);
    UpstoxFeedService stocks=mock(UpstoxFeedService.class);
    MarketCalendarService calendar=mock(MarketCalendarService.class);
    DiscoveryHistoryScheduler scheduler=new DiscoveryHistoryScheduler(db,stocks,calendar);
    scheduler.enabled=true;scheduler.usageRights=true;scheduler.accessToken="test-only";
    scheduler.scheduled();
    verifyNoInteractions(db,stocks,calendar);
  }

  @Test void claimsMappedInstrumentAndUsesExistingAdapter()throws Exception{
    JdbcTemplate db=mock(JdbcTemplate.class);
    UpstoxFeedService stocks=mock(UpstoxFeedService.class);
    DiscoveryHistoryScheduler scheduler=new DiscoveryHistoryScheduler(db,stocks,mock(MarketCalendarService.class));
    scheduler.accessToken="test-only";
    LocalDate end=LocalDate.of(2026,11,20);
    when(db.queryForList(contains("LIMIT 10"),eq("NSE"),eq(end.minusMonths(15)),eq(end),eq(end),eq(end.minusMonths(15)),eq(end),eq(end),eq("NSE"),eq(253),eq(end))).thenReturn(List.of(
      Map.of("id",7L,"instrument_key","NSE_EQ|TEST","candle_count",0L)));
    when(db.update(contains("INSERT INTO discovery_history_attempts"),eq(7L))).thenReturn(1);
    when(stocks.discoveryDailyCandles("test-only","NSE_EQ|TEST",end.minusMonths(15),end)).thenReturn(100);
    scheduler.refreshExchange("NSE",end);
    verify(stocks).discoveryDailyCandles("test-only","NSE_EQ|TEST",end.minusMonths(15),end);
    verify(db).update(contains("status='SUCCESS'"),eq(100),eq(7L));
  }

  @org.junit.jupiter.params.ParameterizedTest
  @org.junit.jupiter.params.provider.ValueSource(longs={120L,200L,201L,252L})
  void existingShortHistoryIsBackfilledForLongTermResearch(long existingCount)throws Exception{
    JdbcTemplate db=mock(JdbcTemplate.class);
    UpstoxFeedService stocks=mock(UpstoxFeedService.class);
    DiscoveryHistoryScheduler scheduler=new DiscoveryHistoryScheduler(db,stocks,mock(MarketCalendarService.class));
    scheduler.accessToken="test-only";
    LocalDate end=LocalDate.of(2026,11,20);
    when(db.queryForList(contains("h.candle_count<?"),eq("NSE"),eq(end.minusMonths(15)),eq(end),eq(end),eq(end.minusMonths(15)),eq(end),eq(end),eq("NSE"),eq(253),eq(end))).thenReturn(List.of(
      Map.of("id",7L,"instrument_key","NSE_EQ|TEST","candle_count",existingCount,"latest_date",end)));
    when(db.update(contains("INSERT INTO discovery_history_attempts"),eq(7L))).thenReturn(1);
    when(stocks.discoveryDailyCandles("test-only","NSE_EQ|TEST",end.minusMonths(15),end)).thenReturn(270);
    scheduler.refreshExchange("NSE",end);
    verify(stocks).discoveryDailyCandles("test-only","NSE_EQ|TEST",end.minusMonths(15),end);
  }

  @Test void sufficientHistoryUsesIncrementalRefresh()throws Exception{
    JdbcTemplate db=mock(JdbcTemplate.class);
    UpstoxFeedService stocks=mock(UpstoxFeedService.class);
    DiscoveryHistoryScheduler scheduler=new DiscoveryHistoryScheduler(db,stocks,mock(MarketCalendarService.class));
    scheduler.accessToken="test-only";
    LocalDate end=LocalDate.of(2026,11,20);
    when(db.queryForList(contains("LIMIT 10"),eq("NSE"),eq(end.minusMonths(15)),eq(end),eq(end),eq(end.minusMonths(15)),eq(end),eq(end),eq("NSE"),eq(253),eq(end))).thenReturn(List.of(
      Map.of("id",7L,"instrument_key","NSE_EQ|TEST","candle_count",253L,"latest_date",end.minusDays(2))));
    when(db.update(contains("INSERT INTO discovery_history_attempts"),eq(7L))).thenReturn(1);
    when(stocks.discoveryDailyCandles("test-only","NSE_EQ|TEST",end.minusDays(1),end)).thenReturn(2);
    scheduler.refreshExchange("NSE",end);
    verify(stocks).discoveryDailyCandles("test-only","NSE_EQ|TEST",end.minusDays(1),end);
  }

  @Test void currentHistoryWithInteriorGapUsesEarliestMissingSession()throws Exception{
    JdbcTemplate db=mock(JdbcTemplate.class);
    UpstoxFeedService stocks=mock(UpstoxFeedService.class);
    DiscoveryHistoryScheduler scheduler=new DiscoveryHistoryScheduler(db,stocks,mock(MarketCalendarService.class));
    scheduler.accessToken="test-only";
    LocalDate end=LocalDate.of(2026,11,20),missing=end.minusDays(9);
    when(db.queryForList(contains("g.first_missing_date IS NOT NULL"),eq("NSE"),eq(end.minusMonths(15)),eq(end),eq(end),
      eq(end.minusMonths(15)),eq(end),eq(end),eq("NSE"),eq(253),eq(end)))
      .thenReturn(List.of(Map.of("id",7L,"instrument_key","NSE_EQ|TEST","candle_count",260L,
        "latest_date",end,"first_missing_date",java.sql.Date.valueOf(missing))));
    when(db.update(contains("INSERT INTO discovery_history_attempts"),eq(7L))).thenReturn(1);
    when(stocks.discoveryDailyCandles("test-only","NSE_EQ|TEST",missing,end)).thenReturn(1);
    scheduler.refreshExchange("NSE",end);
    verify(stocks).discoveryDailyCandles("test-only","NSE_EQ|TEST",missing,end);
    verify(db).update(contains("status='SUCCESS'"),eq(1),eq(7L));
  }

  @Test void sharedCooldownSkipsClaimsAndRequests(){
    JdbcTemplate db=mock(JdbcTemplate.class);
    UpstoxFeedService stocks=mock(UpstoxFeedService.class);
    DiscoveryHistoryScheduler scheduler=new DiscoveryHistoryScheduler(db,stocks,mock(MarketCalendarService.class));
    when(db.queryForObject(contains("operator_feed_cooldown"),eq(Boolean.class))).thenReturn(true);
    scheduler.refreshExchange("NSE",LocalDate.of(2026,11,20));
    verifyNoInteractions(stocks);
    verify(db,never()).update(anyString(),anyLong());
  }

  @Test void providerRejectionStopsRemainingInstrumentRequests()throws Exception{
    JdbcTemplate db=mock(JdbcTemplate.class);
    UpstoxFeedService stocks=mock(UpstoxFeedService.class);
    DiscoveryHistoryScheduler scheduler=new DiscoveryHistoryScheduler(db,stocks,mock(MarketCalendarService.class));
    scheduler.accessToken="test-only";
    LocalDate end=LocalDate.of(2026,11,20);
    when(db.queryForList(contains("LIMIT 10"),eq("NSE"),eq(end.minusMonths(15)),eq(end),eq(end),eq(end.minusMonths(15)),eq(end),eq(end),eq("NSE"),eq(253),eq(end)))
      .thenReturn(List.of(Map.of("id",7L,"instrument_key","NSE_EQ|FIRST","candle_count",0L),
        Map.of("id",8L,"instrument_key","NSE_EQ|SECOND","candle_count",0L)));
    when(db.update(contains("INSERT INTO discovery_history_attempts"),eq(7L))).thenReturn(1);
    when(stocks.discoveryDailyCandles("test-only","NSE_EQ|FIRST",end.minusMonths(15),end))
      .thenThrow(new FeedHttp.ProviderHttpException(429,600));
    scheduler.refreshExchange("NSE",end);
    verify(stocks,never()).discoveryDailyCandles(eq("test-only"),eq("NSE_EQ|SECOND"),any(),any());
    verify(db).update(contains("INSERT INTO operator_feed_cooldown"),eq("PROVIDER_RATE_LIMITED"),eq(600L),eq(60));
  }

  @Test void emptyBackfillCannotBeMarkedSuccessful()throws Exception{
    JdbcTemplate db=mock(JdbcTemplate.class);
    UpstoxFeedService stocks=mock(UpstoxFeedService.class);
    DiscoveryHistoryScheduler scheduler=new DiscoveryHistoryScheduler(db,stocks,mock(MarketCalendarService.class));
    scheduler.accessToken="test-only";
    LocalDate end=LocalDate.of(2026,11,20);
    when(db.queryForList(contains("LIMIT 10"),eq("NSE"),eq(end.minusMonths(15)),eq(end),eq(end),eq(end.minusMonths(15)),eq(end),eq(end),eq("NSE"),eq(253),eq(end)))
      .thenReturn(List.of(Map.of("id",7L,"instrument_key","NSE_EQ|TEST","candle_count",0L)));
    when(db.update(contains("INSERT INTO discovery_history_attempts"),eq(7L))).thenReturn(1);
    scheduler.refreshExchange("NSE",end);
    verify(db).update(contains("status='FAILED'"),eq(7L));
    verify(db,never()).update(contains("status='SUCCESS'"),anyInt(),anyLong());
  }

  @Test void anotherWorkerClaimPreventsDuplicateRequest(){
    JdbcTemplate db=mock(JdbcTemplate.class);
    UpstoxFeedService stocks=mock(UpstoxFeedService.class);
    DiscoveryHistoryScheduler scheduler=new DiscoveryHistoryScheduler(db,stocks,mock(MarketCalendarService.class));
    LocalDate end=LocalDate.of(2026,11,20);
    when(db.queryForList(contains("LIMIT 10"),eq("BSE"),eq(end.minusMonths(15)),eq(end),eq(end),eq(end.minusMonths(15)),eq(end),eq(end),eq("BSE"),eq(253),eq(end))).thenReturn(List.of(
      Map.of("id",7L,"instrument_key","BSE_EQ|TEST","candle_count",0L)));
    scheduler.refreshExchange("BSE",end);
    verifyNoInteractions(stocks);
  }

  @Test void adaptiveAllocationReservesFairSlotsAndKeepsTotalProviderBudget(){
    JdbcTemplate db=mock(JdbcTemplate.class);
    var scheduler=new DiscoveryHistoryScheduler(db,mock(UpstoxFeedService.class),mock(MarketCalendarService.class));
    scheduler.quoteScreenEnabled=true;
    LocalDate end=LocalDate.of(2026,11,26);
    scheduler.refreshExchange("NSE",end);
    verify(db).queryForList(argThat(sql->sql.contains("JOIN discovery_quote_universe")&&sql.contains("CASE WHEN oldest_position=1 THEN 10")&&sql.contains("workload=1 AND position=1")&&sql.contains("workload=0 AND position<=6")&&sql.contains("workload=1 AND position<=4")&&sql.contains("LIMIT 10")),eq("NSE"),eq(end.minusMonths(15)),eq(end),eq(end),eq(end.minusMonths(15)),eq(end),eq(end),eq("NSE"),eq(253),eq(end));
  }
}
