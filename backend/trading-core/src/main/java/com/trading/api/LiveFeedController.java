package com.trading.api;
import com.fasterxml.jackson.databind.JsonNode;
import com.trading.market.*;
import java.time.*;
import java.util.*;
import org.springframework.web.bind.annotation.*;
@RestController @RequestMapping("/api/v1")
public class LiveFeedController {
 private final UpstoxFeedService stocks;private final AmfiFeedService funds;
 public LiveFeedController(UpstoxFeedService stocks,AmfiFeedService funds){this.stocks=stocks;this.funds=funds;}
 @GetMapping("/instruments/search") public List<Map<String,Object>> stockSearch(@RequestParam String q){AuthSecurity.currentUser();return stocks.search(q);}
 @GetMapping("/instruments/quote") public JsonNode quote(@RequestParam String instrumentKey)throws Exception{return stocks.quote(AuthSecurity.currentUser(),instrumentKey);}
 @PostMapping("/instruments/candles/sync") public Map<String,Object> candles(@RequestParam String instrumentKey,@RequestParam LocalDate from,@RequestParam LocalDate to)throws Exception{return Map.of("written",stocks.dailyCandles(AuthSecurity.currentUser(),instrumentKey,from,to));}
 @GetMapping("/mutual-funds/search") public List<Map<String,Object>> fundSearch(@RequestParam String q){AuthSecurity.currentUser();return funds.search(q);}
 @GetMapping("/mutual-funds/{schemeCode}/performance") public Map<String,Object> performance(@PathVariable long schemeCode){AuthSecurity.currentUser();return funds.performance(schemeCode);}
 @PostMapping("/mutual-funds/{schemeCode}/history/sync") public Map<String,Object> history(@PathVariable long schemeCode)throws Exception{AuthSecurity.currentUser();return Map.of("written",funds.history(schemeCode));}
}
