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
 @GetMapping("/fund-outcome-window")
 public Map<String,Object> outcome(HttpServletRequest request,@RequestParam long schemeCode,@RequestParam String from,@RequestParam String through){
  authorization.requireServiceToken(request.getHeader("X-Atlas-Service-Token"));
  try{return research.outcomeWindow(schemeCode,java.time.LocalDate.parse(from),java.time.LocalDate.parse(through));}
  catch(IllegalArgumentException|java.time.DateTimeException ex){throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid fund outcome window");}
 }
 @GetMapping("/fund-history")
 public Map<String,Object> history(HttpServletRequest request,@RequestParam(defaultValue="LARGE_CAP") String category){
  authorization.requireServiceToken(request.getHeader("X-Atlas-Service-Token"));
  try{return research.watch(category);}catch(IllegalArgumentException ex){throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Unsupported category");}
 }
}
