package com.trading.api;

import java.util.Map;
import jakarta.servlet.http.HttpServletRequest;
import com.trading.market.FundHistoryResearchService;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/v1/internal/feed")
public class InternalFundResearchController {
 private final InternalFeedController authorization;
 private final FundHistoryResearchService research;
 public InternalFundResearchController(InternalFeedController authorization,FundHistoryResearchService research){
  this.authorization=authorization;this.research=research;
 }
 @GetMapping("/fund-history")
 public Map<String,Object> history(HttpServletRequest request,@RequestParam(defaultValue="LARGE_CAP") String category){
  authorization.requireServiceToken(request.getHeader("X-Atlas-Service-Token"));
  try{return research.watch(category);}catch(IllegalArgumentException ex){throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Unsupported category");}
 }
}
