package com.trading.market;

import org.junit.jupiter.api.Test;
import static org.mockito.Mockito.*;

class PortfolioRefreshSchedulerTest {
  @Test void disabledDoesNotPoll(){
    PortfolioRefreshService service=mock(PortfolioRefreshService.class);
    PortfolioRefreshScheduler scheduler=new PortfolioRefreshScheduler(service);
    scheduler.enabled=false;
    scheduler.scheduled();
    verifyNoInteractions(service);
  }

  @Test void enabledPollsBoundedBatch(){
    PortfolioRefreshService service=mock(PortfolioRefreshService.class);
    PortfolioRefreshScheduler scheduler=new PortfolioRefreshScheduler(service);
    scheduler.enabled=true;
    scheduler.scheduled();
    verify(service).refreshDue(5);
  }
}
