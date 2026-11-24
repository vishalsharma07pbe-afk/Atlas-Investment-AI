package com.trading.api;

import java.util.Map;
import com.trading.market.PortfolioReviewService;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/portfolio")
public class PortfolioReviewController {
  private final PortfolioReviewService review;
  public PortfolioReviewController(PortfolioReviewService review){this.review=review;}
  @GetMapping("/review")
  public Map<String,Object> review(){return review.current(AuthSecurity.currentUser());}
}
