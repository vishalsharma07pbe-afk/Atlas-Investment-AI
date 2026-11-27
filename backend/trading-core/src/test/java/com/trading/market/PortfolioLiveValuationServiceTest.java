package com.trading.market;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
import static org.junit.jupiter.api.Assertions.*;

class PortfolioLiveValuationServiceTest {
 @Test void acceptsOnlyFreshExactMarketTicksForExplicitOwner()throws Exception{
  var jdbc=mock(JdbcTemplate.class);var mapper=new ObjectMapper();var service=new PortfolioLiveValuationService(jdbc,mapper);
  var owner=UUID.randomUUID();var now=Instant.parse("2026-11-27T06:30:00Z");
  var body=mapper.readTree("""
   {"status":"AVAILABLE","source":"UPSTOX_V3_STREAM","items":[
   {"instrument_key":"NSE_EQ|INE002A01018","price":123,"previous_close":120,"as_of":"2026-11-27T06:29:59Z"},
   {"instrument_key":"NSE_EQ|INE009A01021","price":9,"as_of":"2026-11-27T06:29:00Z"},
   {"instrument_key":"NSE_EQ|INE123A01011","price":90,"as_of":"2026-11-27T06:30:01Z"}]}
   """);
  when(jdbc.update(contains("h.user_id=m.user_id"),argThat(s->s instanceof String str&&str.contains("INE002A01018")&&!str.contains("INE009A01021")&&!str.contains("INE123A01011")),eq(owner))).thenReturn(1);
  assertEquals(1,service.apply(owner,body,now).get("updated"));
  assertEquals(0,service.apply(owner,mapper.readTree("{\"status\":\"UNAVAILABLE\",\"items\":[]}"),now).get("updated"));
  verify(jdbc,times(1)).update(anyString(),anyString(),eq(owner));
 }
}
