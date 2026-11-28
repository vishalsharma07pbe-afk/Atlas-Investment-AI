package com.trading.api;
import java.util.Map;
import jakarta.servlet.http.HttpServletRequest;
import com.trading.market.FundHistoryResearchService;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.server.ResponseStatusException;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
class InternalFundResearchControllerTest {
 @Test void requiresServiceCredentialBeforeReadingPublicFundEvidence(){
  var guard=new InternalFeedController(mock(JdbcTemplate.class),mock(InstrumentController.class),mock(MarketDataController.class),mock(DataHealthController.class),"test-only");
  var research=mock(FundHistoryResearchService.class);
  var controller=new InternalFundResearchController(guard,research);
  var request=mock(HttpServletRequest.class);
  assertThrows(ResponseStatusException.class,()->controller.history(request,"LARGE_CAP"));
  assertThrows(ResponseStatusException.class,()->controller.outcome(request,123456,"2026-08-01","2026-11-20"));
  verifyNoInteractions(research);
  when(request.getHeader("X-Atlas-Service-Token")).thenReturn("test-only");
  when(research.watch("LARGE_CAP")).thenReturn(Map.of("category","LARGE_CAP"));
  assertEquals("LARGE_CAP",controller.history(request,"LARGE_CAP").get("category"));
  var from=java.time.LocalDate.parse("2026-08-01");var through=java.time.LocalDate.parse("2026-11-20");
  when(research.outcomeWindow(123456L,from,through)).thenReturn(Map.of("status","LOCAL_AMFI_OBSERVATIONS"));
  assertEquals("LOCAL_AMFI_OBSERVATIONS",controller.outcome(request,123456,"2026-08-01","2026-11-20").get("status"));
  assertThrows(ResponseStatusException.class,()->controller.outcome(request,123456,"invalid","2026-11-20"));
 }
}
