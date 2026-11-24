package com.trading.market;

import java.time.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;

class DiscoveryHistorySchedulerTest {
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
    when(db.queryForList(contains("LIMIT 2"),eq("NSE"),eq(200),eq(end))).thenReturn(List.of(
      Map.of("id",7L,"instrument_key","NSE_EQ|TEST","candle_count",0L)));
    when(db.update(contains("INSERT INTO discovery_history_attempts"),eq(7L))).thenReturn(1);
    when(stocks.discoveryDailyCandles("test-only","NSE_EQ|TEST",end.minusMonths(12),end)).thenReturn(100);
    scheduler.refreshExchange("NSE",end);
    verify(stocks).discoveryDailyCandles("test-only","NSE_EQ|TEST",end.minusMonths(12),end);
    verify(db).update(contains("status='SUCCESS'"),eq(100),eq(7L));
  }

  @Test void existingShortHistoryIsBackfilledForLongTermResearch()throws Exception{
    JdbcTemplate db=mock(JdbcTemplate.class);
    UpstoxFeedService stocks=mock(UpstoxFeedService.class);
    DiscoveryHistoryScheduler scheduler=new DiscoveryHistoryScheduler(db,stocks,mock(MarketCalendarService.class));
    scheduler.accessToken="test-only";
    LocalDate end=LocalDate.of(2026,11,20);
    when(db.queryForList(contains("h.candle_count<?"),eq("NSE"),eq(200),eq(end))).thenReturn(List.of(
      Map.of("id",7L,"instrument_key","NSE_EQ|TEST","candle_count",120L,"latest_date",end)));
    when(db.update(contains("INSERT INTO discovery_history_attempts"),eq(7L))).thenReturn(1);
    when(stocks.discoveryDailyCandles("test-only","NSE_EQ|TEST",end.minusMonths(12),end)).thenReturn(230);
    scheduler.refreshExchange("NSE",end);
    verify(stocks).discoveryDailyCandles("test-only","NSE_EQ|TEST",end.minusMonths(12),end);
  }

  @Test void sufficientHistoryUsesIncrementalRefresh()throws Exception{
    JdbcTemplate db=mock(JdbcTemplate.class);
    UpstoxFeedService stocks=mock(UpstoxFeedService.class);
    DiscoveryHistoryScheduler scheduler=new DiscoveryHistoryScheduler(db,stocks,mock(MarketCalendarService.class));
    scheduler.accessToken="test-only";
    LocalDate end=LocalDate.of(2026,11,20);
    when(db.queryForList(contains("LIMIT 2"),eq("NSE"),eq(200),eq(end))).thenReturn(List.of(
      Map.of("id",7L,"instrument_key","NSE_EQ|TEST","candle_count",220L,"latest_date",end.minusDays(2))));
    when(db.update(contains("INSERT INTO discovery_history_attempts"),eq(7L))).thenReturn(1);
    when(stocks.discoveryDailyCandles("test-only","NSE_EQ|TEST",end.minusDays(1),end)).thenReturn(2);
    scheduler.refreshExchange("NSE",end);
    verify(stocks).discoveryDailyCandles("test-only","NSE_EQ|TEST",end.minusDays(1),end);
  }

  @Test void anotherWorkerClaimPreventsDuplicateRequest(){
    JdbcTemplate db=mock(JdbcTemplate.class);
    UpstoxFeedService stocks=mock(UpstoxFeedService.class);
    DiscoveryHistoryScheduler scheduler=new DiscoveryHistoryScheduler(db,stocks,mock(MarketCalendarService.class));
    LocalDate end=LocalDate.of(2026,11,20);
    when(db.queryForList(contains("LIMIT 2"),eq("BSE"),eq(200),eq(end))).thenReturn(List.of(
      Map.of("id",7L,"instrument_key","BSE_EQ|TEST","candle_count",0L)));
    scheduler.refreshExchange("BSE",end);
    verifyNoInteractions(stocks);
  }
}
