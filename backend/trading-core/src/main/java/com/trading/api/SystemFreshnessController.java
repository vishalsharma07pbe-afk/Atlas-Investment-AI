package com.trading.api;
import com.trading.market.FreshnessService;
import java.util.*;
import org.springframework.web.bind.annotation.*;
@RestController @RequestMapping("/api/v1/system")
public class SystemFreshnessController {
 private final FreshnessService freshness;
 public SystemFreshnessController(FreshnessService freshness){this.freshness=freshness;}
 @GetMapping("/freshness") public Map<String,Object> freshness(){AuthSecurity.currentUser();List<Map<String,Object>> rows=freshness.snapshot();var funds=freshness.mutualFundSnapshot();return Map.of("instruments",rows,"mutualFunds",funds,"staleCount",rows.stream().filter(r->r.get("alert_id")!=null).count()+funds.stream().filter(r->Boolean.TRUE.equals(r.get("stale"))).count());}
}
