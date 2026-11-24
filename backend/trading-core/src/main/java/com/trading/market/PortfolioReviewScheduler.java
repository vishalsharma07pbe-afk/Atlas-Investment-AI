package com.trading.market;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

@Service
public class PortfolioReviewScheduler {
  private final PortfolioReviewService review;
  @Value("${ATLAS_PORTFOLIO_REVIEW_ENABLED:false}") boolean enabled;
  public PortfolioReviewScheduler(PortfolioReviewService review){this.review=review;}
  @Scheduled(initialDelayString="${atlas.portfolio.review.initial-ms:45000}",
             fixedDelayString="${atlas.portfolio.review.poll-ms:60000}")
  public void scheduled(){if(enabled)review.refreshDue();}
}
