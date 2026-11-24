package com.trading.api;

import java.util.Map;
import com.trading.market.PortfolioReviewService;
import com.trading.market.PortfolioThesisService;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/portfolio")
public class PortfolioReviewController {
  private final PortfolioReviewService review;
  private final PortfolioThesisService thesis;
  public PortfolioReviewController(PortfolioReviewService review,PortfolioThesisService thesis){this.review=review;this.thesis=thesis;}
  @GetMapping("/review")
  public Map<String,Object> review(){return thesis.enrich(review.current(AuthSecurity.currentUser()));}
}
