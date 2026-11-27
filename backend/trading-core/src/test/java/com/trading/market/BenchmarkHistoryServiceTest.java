package com.trading.market;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.LocalDate;
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
