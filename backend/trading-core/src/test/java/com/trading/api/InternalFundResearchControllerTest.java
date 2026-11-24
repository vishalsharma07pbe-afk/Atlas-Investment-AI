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
  verifyNoInteractions(research);
  when(request.getHeader("X-Atlas-Service-Token")).thenReturn("test-only");
  when(research.watch("LARGE_CAP")).thenReturn(Map.of("category","LARGE_CAP"));
  assertEquals("LARGE_CAP",controller.history(request,"LARGE_CAP").get("category"));
 }
}
