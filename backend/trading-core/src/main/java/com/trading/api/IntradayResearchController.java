package com.trading.api;
import java.util.Map;
import com.trading.market.IntradayResearchService;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/market-data")
public class IntradayResearchController {
 private final IntradayResearchService research;
 public IntradayResearchController(IntradayResearchService research){this.research=research;}
 @GetMapping("/intraday-research")
 public Map<String,Object> current(){AuthSecurity.currentUser();return research.current();}
}
