package com.trading.market;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.LocalDate;
import java.util.Map;
import java.util.UUID;
import static org.mockito.ArgumentMatchers.*;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class BenchmarkHistoryServiceTest {
  private final ObjectMapper json=new ObjectMapper();
  private final LocalDate date=LocalDate.of(2025,1,2);
  @Test void parsesDailyPriceIndexIncludingZeroVolume()throws Exception{
    var candles=BenchmarkHistoryService.parse(json.readTree("""
      {"status":"success","data":{"candles":[["2025-01-02T00:00:00+05:30",100,110,90,105,0,0]]}}
      """),date,date);
    assertEquals(1,candles.size());
    assertEquals(date,candles.getFirst().date());
    assertEquals(0,candles.getFirst().volume());
  }
  @Test void rejectsMalformedDuplicateAndOutOfRangeHistory()throws Exception{
    for(String rows:new String[]{
      "[[\"2025-01-02T00:00:00+05:30\",100,80,90,105,0]]",
      "[[\"2025-01-03T00:00:00+05:30\",100,110,90,105,0]]",
      "[[\"2025-01-02T00:00:00+05:30\",100,110,90,105,0],[\"2025-01-02T00:00:00+05:30\",100,110,90,105,0]]",
      "[]"}){
      var body=json.readTree("{\"status\":\"success\",\"data\":{\"candles\":"+rows+"}}");
      assertThrows(IllegalArgumentException.class,()->BenchmarkHistoryService.parse(body,date,date));
    }
  }
  @Test void sectorIndexHistoryUrlIsFixedAndEncoded(){
    var url=BenchmarkHistoryService.historyUrl("NSE_INDEX|Nifty Bank",date,date);
    assertTrue(url.contains("NSE_INDEX%7CNifty%20Bank/days/1/"));
    assertThrows(IllegalArgumentException.class,()->BenchmarkHistoryService.historyUrl("https://example.org",date,date));
    assertEquals(6,BenchmarkHistoryService.SECTOR_KEYS.size());
  }
  @Test void schedulerDoesNotSkipUnknownOrSpecialPriorSession(){
    var db=mock(JdbcTemplate.class);
    var service=mock(BenchmarkHistoryService.class);
    var calendar=mock(MarketCalendarService.class);
    var scheduler=new BenchmarkHistoryScheduler(db,service,calendar);
    scheduler.enabled=true;scheduler.rights=true;scheduler.entitlement=true;scheduler.token="test-only";
    for(String phase:new String[]{"CALENDAR_UNVERIFIED","SPECIAL_SESSION_UNSUPPORTED"}){
      when(calendar.sessionContext(eq("NSE"),any())).thenReturn(Map.of("phase",phase));
      scheduler.scheduled();
    }
    verifyNoInteractions(db,service);
  }
  @Test void partialBenchmarkResponseCannotMarkNewTargetSuccessful()throws Exception{
    var db=mock(JdbcTemplate.class);
    var service=mock(BenchmarkHistoryService.class);
    var scheduler=new BenchmarkHistoryScheduler(db,service,mock(MarketCalendarService.class));
    scheduler.token="test-only";
    when(service.ensureIndex()).thenReturn(7L);
    when(db.update(contains("INSERT INTO discovery_history_attempts"),eq(7L),eq(date),any(UUID.class))).thenReturn(1);
    when(service.refresh(7L,"test-only",date.minusDays(470),date)).thenReturn(3);
    assertTrue(scheduler.refreshOne(date,BenchmarkHistoryService.KEY));
    verify(db).update(contains("UPDATE discovery_history_attempts SET status=?"),eq("FAILED"),eq(3),eq(360),eq(7L),any(UUID.class));
    verify(service,times(2)).targetPresent(7L,date);
  }
  @Test void schedulerRequiresAllPermissionsAndToken(){
    var db=mock(JdbcTemplate.class);
    var service=mock(BenchmarkHistoryService.class);
    var calendar=mock(MarketCalendarService.class);
    var scheduler=new BenchmarkHistoryScheduler(db,service,calendar);
    scheduler.enabled=true;scheduler.rights=true;scheduler.token="test-token";
    scheduler.scheduled();
    scheduler.entitlement=true;scheduler.token="";
    scheduler.scheduled();
    verifyNoInteractions(db,service,calendar);
  }
}
