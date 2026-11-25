package com.trading.market;

import java.time.Instant;
import java.time.LocalTime;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

/** Local evening capture. The persisted owner/date key prevents restart duplicates. */
@Service
public class PortfolioValuationHistoryScheduler {
  private final PortfolioValuationHistoryService history;
  @Value("${ATLAS_PORTFOLIO_VALUATION_HISTORY_ENABLED:false}") boolean enabled;
  public PortfolioValuationHistoryScheduler(PortfolioValuationHistoryService history){this.history=history;}

  @Scheduled(initialDelayString="${atlas.portfolio.valuation.initial-ms:90000}",
             fixedDelayString="${atlas.portfolio.valuation.poll-ms:300000}")
  public void scheduled(){captureAt(Instant.now());}

  void captureAt(Instant instant){
    if(enabled&&!instant.atZone(MarketCalendarService.IST).toLocalTime().isBefore(LocalTime.of(22,0)))
      history.captureDue(5);
  }
}
