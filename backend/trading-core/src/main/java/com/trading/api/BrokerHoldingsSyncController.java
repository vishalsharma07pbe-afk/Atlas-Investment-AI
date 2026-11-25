package com.trading.api;

import com.trading.market.BrokerHoldingsSyncService;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

/** Only the signed-in owner may view/change their reconciliation preference. */
@RestController
@RequestMapping("/api/v1/broker/upstox/holdings-sync")
public class BrokerHoldingsSyncController {
  private final BrokerHoldingsSyncService sync;
  public BrokerHoldingsSyncController(BrokerHoldingsSyncService sync){this.sync=sync;}
  public record Preference(Boolean enabled){}
  @GetMapping public Map<String,Object> status(){return sync.status(AuthSecurity.currentUser());}
  @PutMapping public Map<String,Object> preference(@RequestBody Preference input){
    if(input==null||input.enabled()==null)
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Explicit sync preference required");
    return sync.preference(AuthSecurity.currentUser(),input.enabled());
  }
}
