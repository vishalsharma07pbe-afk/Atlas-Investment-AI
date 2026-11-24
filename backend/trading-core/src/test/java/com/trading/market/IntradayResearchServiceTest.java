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
 @Test void neverRequestsWithoutEntitlement(){
  var jdbc=mock(JdbcTemplate.class);var stocks=mock(UpstoxFeedService.class);var calendar=mock(MarketCalendarService.class);
  var service=new IntradayResearchService(jdbc,stocks,calendar);
  service.enabled=true;service.rights=true;service.token="test-only";
  service.scheduled();verifyNoInteractions(jdbc,stocks,calendar);
 }
}
