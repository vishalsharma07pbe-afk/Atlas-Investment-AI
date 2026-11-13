package com.trading.api;
import java.time.Instant;
import java.util.Map;
import org.springframework.web.bind.annotation.*;
@RestController
@RequestMapping("/api/v1")
public class HealthController {
  @GetMapping("/health")
  public Map<String,Object> health() {
    return Map.of("status","UP","service","trading-core","mode","RESEARCH_ONLY","timestamp",Instant.now().toString());
  }
}
