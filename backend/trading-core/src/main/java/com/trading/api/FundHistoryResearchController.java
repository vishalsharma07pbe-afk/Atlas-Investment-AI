package com.trading.api;
import java.util.Map;
import com.trading.market.FundHistoryResearchService;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.HttpStatus;

@RestController
@RequestMapping("/api/v1/mutual-funds")
public class FundHistoryResearchController {
 private final FundHistoryResearchService research;
 public FundHistoryResearchController(FundHistoryResearchService research){this.research=research;}
 @GetMapping("/historical-watch")
 public Map<String,Object> watch(@RequestParam(defaultValue="LARGE_CAP") String category){
  AuthSecurity.currentUser();
  try{return research.watch(category);}catch(IllegalArgumentException ex){throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Unsupported category");}
 }
}
