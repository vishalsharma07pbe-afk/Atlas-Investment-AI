package com.trading.market;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

@Service
public class PortfolioRefreshScheduler {
  private final PortfolioRefreshService refresh;
  @Value("${ATLAS_PORTFOLIO_AUTO_REFRESH_ENABLED:false}") boolean enabled;
  public PortfolioRefreshScheduler(PortfolioRefreshService refresh){this.refresh=refresh;}

  @Scheduled(initialDelayString="${atlas.portfolio.refresh.initial-ms:30000}",
             fixedDelayString="${atlas.portfolio.refresh.poll-ms:60000}")
  public void scheduled(){
    if(enabled)refresh.refreshDue(5);
  }
}
