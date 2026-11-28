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
    verify(db).queryForList(argThat(sql->sql.contains("h.candle_count>=25 AND h.latest_date<?")&&sql.contains("workload=0 AND position<=8")&&sql.contains("workload=1 AND position<=2")&&sql.contains("workload,position LIMIT 10")),eq("NSE"),eq(end.minusMonths(15)),eq(end),eq(end),eq(end.minusMonths(15)),eq(end),eq(end),eq("NSE"),eq(253),eq(end),eq(end),eq(end));
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

  @Test void priorSessionDoesNotSkipUnknownOrUnsupportedNewerDate(){
    var calendar=mock(MarketCalendarService.class);
    var scheduler=new DiscoveryHistoryScheduler(mock(JdbcTemplate.class),mock(UpstoxFeedService.class),calendar);
    LocalDate today=LocalDate.of(2026,11,23);
    java.util.function.Function<LocalDate,Instant> noon=d->d.atTime(12,0).atZone(MarketCalendarService.IST).toInstant();
    when(calendar.sessionContext("NSE",noon.apply(today.minusDays(1)))).thenReturn(Map.of("phase","CLOSED"));
    when(calendar.sessionContext("NSE",noon.apply(today.minusDays(2)))).thenReturn(Map.of("phase","CLOSED"));
    when(calendar.sessionContext("NSE",noon.apply(today.minusDays(3)))).thenReturn(Map.of("phase","MARKET_HOURS"));
    org.junit.jupiter.api.Assertions.assertEquals(today.minusDays(3),scheduler.verifiedPriorSession("NSE",today));
    for(String phase:List.of("CALENDAR_UNVERIFIED","SPECIAL_SESSION_UNSUPPORTED")){
      when(calendar.sessionContext("NSE",noon.apply(today.minusDays(1)))).thenReturn(Map.of("phase",phase));
      org.junit.jupiter.api.Assertions.assertNull(scheduler.verifiedPriorSession("NSE",today));
    }
  }

  @Test void claimsMappedInstrumentAndUsesExistingAdapter()throws Exception{
    JdbcTemplate db=mock(JdbcTemplate.class);
    UpstoxFeedService stocks=mock(UpstoxFeedService.class);
    DiscoveryHistoryScheduler scheduler=new DiscoveryHistoryScheduler(db,stocks,mock(MarketCalendarService.class));
    scheduler.accessToken="test-only";
    LocalDate end=LocalDate.of(2026,11,20);
    when(db.queryForList(contains("LIMIT 10"),eq("NSE"),eq(end.minusMonths(15)),eq(end),eq(end),eq(end.minusMonths(15)),eq(end),eq(end),eq("NSE"),eq(253),eq(end),eq(end),eq(end))).thenReturn(List.of(
      Map.of("id",7L,"instrument_key","NSE_EQ|TEST","candle_count",0L)));
    when(db.update(contains("INSERT INTO discovery_history_attempts"),eq(7L),eq(end),any(UUID.class))).thenReturn(1);
    when(stocks.discoveryDailyCandles("test-only","NSE_EQ|TEST",end.minusMonths(15),end)).thenReturn(100);
    when(db.queryForObject(contains("FROM market_candles"),eq(Boolean.class),eq(7L),eq(end),eq(end))).thenReturn(true);
    scheduler.refreshExchange("NSE",end);
    verify(stocks).discoveryDailyCandles("test-only","NSE_EQ|TEST",end.minusMonths(15),end);
    verify(db).update(contains("UPDATE discovery_history_attempts SET status=?"),eq("SUCCESS"),eq(100),eq(720),eq(7L),any(UUID.class));
  }

  @org.junit.jupiter.params.ParameterizedTest
  @org.junit.jupiter.params.provider.ValueSource(longs={120L,200L,201L,252L})
  void existingShortHistoryIsBackfilledForLongTermResearch(long existingCount)throws Exception{
    JdbcTemplate db=mock(JdbcTemplate.class);
    UpstoxFeedService stocks=mock(UpstoxFeedService.class);
    DiscoveryHistoryScheduler scheduler=new DiscoveryHistoryScheduler(db,stocks,mock(MarketCalendarService.class));
    scheduler.accessToken="test-only";
    LocalDate end=LocalDate.of(2026,11,20);
    when(db.queryForList(contains("h.candle_count<?"),eq("NSE"),eq(end.minusMonths(15)),eq(end),eq(end),eq(end.minusMonths(15)),eq(end),eq(end),eq("NSE"),eq(253),eq(end),eq(end),eq(end))).thenReturn(List.of(
      Map.of("id",7L,"instrument_key","NSE_EQ|TEST","candle_count",existingCount,"latest_date",end)));
    when(db.update(contains("INSERT INTO discovery_history_attempts"),eq(7L),eq(end),any(UUID.class))).thenReturn(1);
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
    when(db.queryForList(contains("LIMIT 10"),eq("NSE"),eq(end.minusMonths(15)),eq(end),eq(end),eq(end.minusMonths(15)),eq(end),eq(end),eq("NSE"),eq(253),eq(end),eq(end),eq(end))).thenReturn(List.of(
      Map.of("id",7L,"instrument_key","NSE_EQ|TEST","candle_count",253L,"latest_date",end.minusDays(2))));
    when(db.update(contains("INSERT INTO discovery_history_attempts"),eq(7L),eq(end),any(UUID.class))).thenReturn(1);
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
      eq(end.minusMonths(15)),eq(end),eq(end),eq("NSE"),eq(253),eq(end),eq(end),eq(end)))
      .thenReturn(List.of(Map.of("id",7L,"instrument_key","NSE_EQ|TEST","candle_count",260L,
        "latest_date",end,"first_missing_date",java.sql.Date.valueOf(missing))));
    when(db.update(contains("INSERT INTO discovery_history_attempts"),eq(7L),eq(end),any(UUID.class))).thenReturn(1);
    when(stocks.discoveryDailyCandles("test-only","NSE_EQ|TEST",missing,end)).thenReturn(1);
    when(db.queryForObject(contains("FROM market_candles"),eq(Boolean.class),eq(7L),eq(end),eq(end))).thenReturn(true);
    scheduler.refreshExchange("NSE",end);
    verify(stocks).discoveryDailyCandles("test-only","NSE_EQ|TEST",missing,end);
    verify(db).update(contains("UPDATE discovery_history_attempts SET status=?"),eq("SUCCESS"),eq(1),eq(720),eq(7L),any(UUID.class));
  }

  @Test void staleEstablishedShortHistoryRecoversLatestBeforeExpanding()throws Exception{
    JdbcTemplate db=mock(JdbcTemplate.class);
    UpstoxFeedService stocks=mock(UpstoxFeedService.class);
    var scheduler=new DiscoveryHistoryScheduler(db,stocks,mock(MarketCalendarService.class));
    scheduler.accessToken="test-only";
    LocalDate end=LocalDate.of(2026,11,20);
    when(db.queryForList(contains("LIMIT 10"),eq("NSE"),eq(end.minusMonths(15)),eq(end),eq(end),eq(end.minusMonths(15)),eq(end),eq(end),eq("NSE"),eq(253),eq(end),eq(end),eq(end))).thenReturn(List.of(
      Map.of("id",7L,"instrument_key","NSE_EQ|TEST","candle_count",50L,"latest_date",end.minusDays(2),"first_missing_date",end.minusDays(20))));
    when(db.update(contains("INSERT INTO discovery_history_attempts"),eq(7L),eq(end),any(UUID.class))).thenReturn(1);
    when(stocks.discoveryDailyCandles("test-only","NSE_EQ|TEST",end.minusDays(1),end)).thenReturn(1);
    scheduler.refreshExchange("NSE",end);
    verify(stocks).discoveryDailyCandles("test-only","NSE_EQ|TEST",end.minusDays(1),end);
    // A partial response may write rows but the requested latest session is absent.
    verify(db).update(contains("UPDATE discovery_history_attempts SET status=?"),eq("FAILED"),eq(1),eq(360),eq(7L),any(UUID.class));
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
    when(db.queryForList(contains("LIMIT 10"),eq("NSE"),eq(end.minusMonths(15)),eq(end),eq(end),eq(end.minusMonths(15)),eq(end),eq(end),eq("NSE"),eq(253),eq(end),eq(end),eq(end)))
      .thenReturn(List.of(Map.of("id",7L,"instrument_key","NSE_EQ|FIRST","candle_count",0L),
        Map.of("id",8L,"instrument_key","NSE_EQ|SECOND","candle_count",0L)));
    when(db.update(contains("INSERT INTO discovery_history_attempts"),eq(7L),eq(end),any(UUID.class))).thenReturn(1);
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
    when(db.queryForList(contains("LIMIT 10"),eq("NSE"),eq(end.minusMonths(15)),eq(end),eq(end),eq(end.minusMonths(15)),eq(end),eq(end),eq("NSE"),eq(253),eq(end),eq(end),eq(end)))
      .thenReturn(List.of(Map.of("id",7L,"instrument_key","NSE_EQ|TEST","candle_count",0L)));
    when(db.update(contains("INSERT INTO discovery_history_attempts"),eq(7L),eq(end),any(UUID.class))).thenReturn(1);
    scheduler.refreshExchange("NSE",end);
    verify(db).update(contains("UPDATE discovery_history_attempts SET status=?"),eq("FAILED"),eq(0),eq(360),eq(7L),any(UUID.class));
    verify(db,never()).update(contains("UPDATE discovery_history_attempts SET status=?"),eq("SUCCESS"),anyInt(),anyInt(),anyLong(),any(UUID.class));
  }

  @Test void anotherWorkerClaimPreventsDuplicateRequest(){
    JdbcTemplate db=mock(JdbcTemplate.class);
    UpstoxFeedService stocks=mock(UpstoxFeedService.class);
    DiscoveryHistoryScheduler scheduler=new DiscoveryHistoryScheduler(db,stocks,mock(MarketCalendarService.class));
    LocalDate end=LocalDate.of(2026,11,20);
    when(db.queryForList(contains("LIMIT 10"),eq("BSE"),eq(end.minusMonths(15)),eq(end),eq(end),eq(end.minusMonths(15)),eq(end),eq(end),eq("BSE"),eq(253),eq(end),eq(end),eq(end))).thenReturn(List.of(
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
    verify(db).queryForList(argThat(sql->sql.contains("JOIN discovery_quote_universe")&&sql.contains("CASE WHEN oldest_position=1 THEN 10")&&sql.contains("workload=1 AND position=1")&&sql.contains("workload=0 AND position<=6")&&sql.contains("workload=1 AND position<=4")&&sql.contains("LIMIT 10")),eq("NSE"),eq(end.minusMonths(15)),eq(end),eq(end),eq(end.minusMonths(15)),eq(end),eq(end),eq("NSE"),eq(253),eq(end),eq(end),eq(end));
  }
}
