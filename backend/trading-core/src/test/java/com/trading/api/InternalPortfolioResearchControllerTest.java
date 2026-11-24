package com.trading.api;
import java.util.*;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.server.ResponseStatusException;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
class InternalPortfolioResearchControllerTest{
 @Test void identitiesRequireServiceCredential(){
  var jdbc=mock(JdbcTemplate.class);
  var guard=new InternalFeedController(jdbc,mock(InstrumentController.class),mock(MarketDataController.class),mock(DataHealthController.class),"test-only");
  var controller=new InternalPortfolioResearchController(jdbc,guard);
  var request=mock(HttpServletRequest.class);
  assertThrows(ResponseStatusException.class,()->controller.identities(request));verifyNoInteractions(jdbc);
  when(request.getHeader("X-Atlas-Service-Token")).thenReturn("test-only");
  when(jdbc.queryForList(contains("SELECT DISTINCT isin,exchange"))).thenReturn(List.of(Map.of("isin","INE002A01018","exchange","NSE")));
  assertEquals(Set.of("isin","exchange"),controller.identities(request).getFirst().keySet());
 }
}
