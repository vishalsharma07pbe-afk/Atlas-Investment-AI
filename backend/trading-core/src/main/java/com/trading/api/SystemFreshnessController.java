package com.trading.api;
import com.trading.market.FreshnessService;
import java.util.*;
import org.springframework.web.bind.annotation.*;
@RestController @RequestMapping("/api/v1/system")
public class SystemFreshnessController {
 private final FreshnessService freshness;
 public SystemFreshnessController(FreshnessService freshness){this.freshness=freshness;}
 @GetMapping("/freshness") public Map<String,Object> freshness(){AuthSecurity.currentUser();List<Map<String,Object>> rows=freshness.snapshot();return Map.of("instruments",rows,"staleCount",rows.stream().filter(r->r.get("alert_id")!=null).count());}
}
