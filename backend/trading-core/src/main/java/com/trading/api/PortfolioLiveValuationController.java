package com.trading.api;

import com.trading.market.PortfolioLiveValuationService;
import java.util.Map;
import org.springframework.web.bind.annotation.*;

/** Authenticated, read-only-market price refresh, never broker account access. */
@RestController
@RequestMapping("/api/v1/portfolio")
public class PortfolioLiveValuationController {
 private final PortfolioLiveValuationService service;
 public PortfolioLiveValuationController(PortfolioLiveValuationService service){this.service=service;}
 @PostMapping("/refresh-live-prices")
 public Map<String,Object> refresh(){return service.refresh(AuthSecurity.currentUser());}
}
