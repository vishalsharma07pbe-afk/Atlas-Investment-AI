package com.trading.api;

import com.trading.market.PortfolioRefreshService;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.*;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/v1/portfolio")
public class PortfolioController {
  private final JdbcTemplate jdbc;
  private final PortfolioRefreshService refreshService;
  public PortfolioController(JdbcTemplate jdbc,PortfolioRefreshService refreshService) {
    this.jdbc = jdbc;this.refreshService=refreshService;
  }

  public record HoldingInput(String symbol, String assetType, BigDecimal quantity,
                             BigDecimal averageCost, BigDecimal lastPrice, String notes) {}
  public record HistoricalInvestmentInput(String symbol,String displayName,String assetType,
      BigDecimal quantity,BigDecimal averageCost,BigDecimal exitPrice,
      LocalDate openedOn,LocalDate closedOn,String notes) {}

  @GetMapping("/holdings")
  public List<Map<String,Object>> holdings() {
    return jdbc.queryForList("""
      SELECT id,symbol,asset_type,quantity,average_cost,last_price,previous_close,price_as_of,notes,
      quantity*average_cost AS invested,
      CASE WHEN last_price IS NOT NULL THEN quantity*last_price ELSE NULL END AS market_value,
      CASE WHEN last_price IS NOT NULL THEN quantity*(last_price-average_cost) ELSE NULL END AS unrealized_pnl,
      CASE WHEN last_price IS NOT NULL AND previous_close IS NOT NULL
        THEN quantity*(last_price-previous_close) ELSE NULL END AS one_day_change
      FROM personal_holdings WHERE user_id=? ORDER BY asset_type,symbol
      """,AuthSecurity.currentUser());
  }

  @PostMapping("/holdings")
  public Map<String,Object> save(@RequestBody HoldingInput input) {
    if (input == null || input.symbol() == null || !input.symbol().trim().matches("[A-Za-z0-9._&-]{1,50}"))
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid symbol");
    String symbol=input.symbol().trim().toUpperCase(Locale.ROOT);
    if (!List.of("EQUITY","MUTUAL_FUND").contains(input.assetType()))
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid asset type");
    if (input.quantity()==null || input.quantity().signum()<=0 || input.averageCost()==null || input.averageCost().signum()<0 ||
        (input.lastPrice()!=null && input.lastPrice().signum()<0))
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid quantity or price");
    if (input.notes()!=null && input.notes().length()>500)
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Notes too long");
    jdbc.update("""
      INSERT INTO personal_holdings(user_id,symbol,asset_type,quantity,average_cost,last_price,price_as_of,notes)
      VALUES (?,?,?,?,?,?,CASE WHEN ? THEN now() ELSE NULL END,?)
      ON CONFLICT(user_id,symbol,asset_type) DO UPDATE SET quantity=EXCLUDED.quantity,
      average_cost=EXCLUDED.average_cost,last_price=EXCLUDED.last_price,
      price_as_of=EXCLUDED.price_as_of,notes=EXCLUDED.notes,updated_at=now()
      """,AuthSecurity.currentUser(),symbol,input.assetType(),input.quantity(),input.averageCost(),input.lastPrice(),input.lastPrice()!=null,input.notes());
    return Map.of("saved",true,"symbol",symbol);
  }

  @DeleteMapping("/holdings/{id}")
  public Map<String,Object> delete(@PathVariable long id) {
    int deleted=jdbc.update("DELETE FROM personal_holdings WHERE id=? AND user_id=?",id,AuthSecurity.currentUser());
    if(deleted==0) throw new ResponseStatusException(HttpStatus.NOT_FOUND,"Holding not found");
    return Map.of("deleted",true);
  }

  @GetMapping("/history")
  public List<Map<String,Object>> historicalInvestments(){
    return jdbc.queryForList("""
      SELECT id,symbol,display_name,asset_type,quantity,average_cost,exit_price,
        opened_on,closed_on,notes,quantity*average_cost AS invested,
        quantity*exit_price AS exit_value,
        quantity*(exit_price-average_cost) AS realized_pnl
      FROM historical_investments WHERE user_id=?
      ORDER BY closed_on DESC,created_at DESC
      """,AuthSecurity.currentUser());
  }

  @PostMapping("/history")
  public Map<String,Object> saveHistoricalInvestment(@RequestBody HistoricalInvestmentInput input){
    if(input==null||input.symbol()==null||!input.symbol().trim().matches("[A-Za-z0-9._&-]{1,50}"))
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid investment identifier");
    String asset=input.assetType()==null?"":input.assetType().trim().toUpperCase(Locale.ROOT);
    if(!Set.of("EQUITY","MUTUAL_FUND").contains(asset))
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid investment type");
    if(input.quantity()==null||input.quantity().signum()<=0||input.averageCost()==null||input.averageCost().signum()<0||
       input.exitPrice()==null||input.exitPrice().signum()<0)
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Quantity and prices must be valid");
    LocalDate closed=input.closedOn();
    if(closed==null||closed.isAfter(LocalDate.now())||closed.isBefore(LocalDate.of(1970,1,1))||
       (input.openedOn()!=null&&input.openedOn().isAfter(closed)))
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid investment dates");
    String display=input.displayName()==null?null:input.displayName().trim();
    if(display!=null&&display.length()>300)throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Name is too long");
    String notes=input.notes()==null?null:input.notes().trim();
    if(notes!=null&&notes.length()>500)throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Notes are too long");
    UUID id=jdbc.queryForObject("""
      INSERT INTO historical_investments(user_id,symbol,display_name,asset_type,quantity,
        average_cost,exit_price,opened_on,closed_on,notes)
      VALUES (?,?,?,?,?,?,?,?,?,?) RETURNING id
      """,UUID.class,AuthSecurity.currentUser(),input.symbol().trim().toUpperCase(Locale.ROOT),display,
      asset,input.quantity(),input.averageCost(),input.exitPrice(),input.openedOn(),closed,notes);
    return Map.of("saved",true,"id",id);
  }

  @DeleteMapping("/history/{id}")
  public Map<String,Boolean> deleteHistoricalInvestment(@PathVariable UUID id){
    int changed=jdbc.update("DELETE FROM historical_investments WHERE id=? AND user_id=?",id,AuthSecurity.currentUser());
    if(changed==0)throw new ResponseStatusException(HttpStatus.NOT_FOUND,"Historical investment not found");
    return Map.of("deleted",true);
  }

  @GetMapping("/analysis")
  public Map<String,Object> analysis() {
    List<Map<String,Object>> rows=holdings();
    BigDecimal invested=BigDecimal.ZERO, valued=BigDecimal.ZERO, knownCost=BigDecimal.ZERO;
    int unpriced=0;
    for(Map<String,Object> row:rows) {
      BigDecimal cost=(BigDecimal)row.get("invested"); invested=invested.add(cost);
      if(row.get("market_value")!=null){valued=valued.add((BigDecimal)row.get("market_value"));knownCost=knownCost.add(cost);}else unpriced++;
    }
    List<String> flags=new ArrayList<>();
    if(unpriced>0) flags.add(unpriced+" holding(s) have no manually entered price; valuation is incomplete.");
    if(rows.size()>0 && rows.size()<5) flags.add("Concentration watch: fewer than five holdings. Diversification needs review.");
    if(valued.signum()>0) for(Map<String,Object> row:rows) if(row.get("market_value")!=null) {
      BigDecimal weight=((BigDecimal)row.get("market_value")).divide(valued,8,java.math.RoundingMode.HALF_UP);
      if(weight.compareTo(new BigDecimal("0.25"))>0) flags.add(row.get("symbol")+" exceeds 25% of currently valued holdings.");
    }
    Map<String,Object> result=new LinkedHashMap<>();
    result.put("holdingCount",rows.size());result.put("invested",invested);
    result.put("pricedMarketValue",valued);result.put("pricedCostBasis",knownCost);
    result.put("pricedUnrealizedPnl",valued.subtract(knownCost));
    result.put("unpricedHoldings",unpriced);result.put("valuationComplete",unpriced==0);
    result.put("riskFlags",flags);result.put("recommendationStatus","UNAVAILABLE_NO_VERIFIED_MARKET_DATA");
    return result;
  }

  /** Refresh the signed-in user's saved valuations from authorized sources.
   * This never creates, removes, buys or sells a holding. One failed symbol does
   * not prevent other holdings from updating. */
  @PostMapping("/refresh-prices")
  public Map<String,Object> refreshPrices(@RequestParam(defaultValue="false") boolean includeHistory){
    return refreshService.refreshUser(AuthSecurity.currentUser(),includeHistory);
  }
}
