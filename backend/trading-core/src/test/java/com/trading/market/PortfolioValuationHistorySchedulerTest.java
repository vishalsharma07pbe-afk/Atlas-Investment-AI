package com.trading.market;

import java.time.Instant;
import org.junit.jupiter.api.Test;
import static org.mockito.Mockito.*;

class PortfolioValuationHistorySchedulerTest {
  @Test void disabledOrBeforeEveningCutoffDoesNotCapture(){
    var history=mock(PortfolioValuationHistoryService.class);
    var scheduler=new PortfolioValuationHistoryScheduler(history);
    scheduler.enabled=false;
    scheduler.captureAt(Instant.parse("2026-11-25T17:00:00Z"));
    scheduler.enabled=true;
    scheduler.captureAt(Instant.parse("2026-11-25T16:29:59Z"));
    scheduler.captureAt(Instant.parse("2026-11-25T18:30:00Z"));
    verifyNoInteractions(history);
  }

  @Test void eveningWindowUsesBoundedBatch(){
    var history=mock(PortfolioValuationHistoryService.class);
    var scheduler=new PortfolioValuationHistoryScheduler(history);
    scheduler.enabled=true;
    scheduler.captureAt(Instant.parse("2026-11-25T16:30:00Z"));
    scheduler.captureAt(Instant.parse("2026-11-25T18:29:59Z"));
    verify(history,times(2)).captureDue(5);
  }
}
