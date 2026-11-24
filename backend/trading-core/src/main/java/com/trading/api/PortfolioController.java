package com.trading.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.trading.market.UpstoxFeedService;
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
  private final UpstoxFeedService upstox;
  public PortfolioController(JdbcTemplate jdbc,UpstoxFeedService upstox) {
    this.jdbc = jdbc;this.upstox=upstox;
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
    UUID user=AuthSecurity.currentUser();
    List<Map<String,Object>> rows=jdbc.queryForList("""
      SELECT id,symbol,asset_type FROM personal_holdings
      WHERE user_id=? ORDER BY asset_type,symbol LIMIT 200
      """,user);
    int updated=0,historySynced=0;List<Map<String,String>> skipped=new ArrayList<>();
    for(Map<String,Object> row:rows){
      long id=((Number)row.get("id")).longValue();
      String symbol=String.valueOf(row.get("symbol"));
      try{
        if("EQUITY".equals(row.get("asset_type"))){
          List<String> keys=jdbc.queryForList("""
            SELECT instrument_key FROM upstox_instrument_map
            WHERE upper(trading_symbol)=upper(?)
            ORDER BY CASE WHEN exchange_code='NSE' THEN 0 ELSE 1 END,
              CASE WHEN instrument_type='EQ' THEN 0 ELSE 1 END,instrument_key LIMIT 1
            """,String.class,symbol);
          if(keys.isEmpty())throw new IllegalStateException("INSTRUMENT_NOT_MAPPED");
          String instrumentKey=keys.get(0);
          JsonNode quote=upstox.quote(user,instrumentKey);
          BigDecimal price=quote.path("ltp").decimalValue();
          BigDecimal previous=quote.path("previous_close").isNumber()?quote.path("previous_close").decimalValue():null;
          jdbc.update("UPDATE personal_holdings SET last_price=?,previous_close=?,price_as_of=now(),updated_at=now() WHERE id=? AND user_id=?",
            price,previous,id,user);updated++;
          if(includeHistory){
            Map<String,Object> history=jdbc.queryForMap("""
              SELECT count(c.*) candle_count,max(c.candle_time)::date latest_date
              FROM instruments i JOIN exchanges e ON e.id=i.exchange_id
              LEFT JOIN market_candles c ON c.instrument_id=i.id AND c.timeframe='1d'
                AND c.is_complete AND c.quality_status IN ('VALIDATED_MANUAL','PROVIDER_VALIDATED')
              JOIN upstox_instrument_map m ON m.exchange_code=e.code AND m.trading_symbol=i.symbol
              WHERE m.instrument_key=? GROUP BY i.id
              """,instrumentKey);
            long count=((Number)history.get("candle_count")).longValue();
            LocalDate latest=history.get("latest_date") instanceof java.sql.Date d?d.toLocalDate():null;
            if(count<21||latest==null||latest.isBefore(LocalDate.now().minusDays(5))){
              try{historySynced+=upstox.dailyCandles(user,instrumentKey,LocalDate.now().minusMonths(6),LocalDate.now());}
              catch(Exception historyError){skipped.add(Map.of("symbol",symbol,"reason","HISTORY_SYNC_FAILED"));}
            }
          }
        }else if(symbol.matches("\\d+")){
          List<Map<String,Object>> nav=jdbc.queryForList("""
            SELECT nav,nav_date FROM mutual_fund_nav WHERE scheme_code=?
            ORDER BY nav_date DESC LIMIT 2
            """,Long.parseLong(symbol));
          if(nav.isEmpty())throw new IllegalStateException("NAV_NOT_AVAILABLE");
          Object previous=nav.size()>1?nav.get(1).get("nav"):null;
          jdbc.update("UPDATE personal_holdings SET last_price=?,previous_close=?,price_as_of=?::date,updated_at=now() WHERE id=? AND user_id=?",
            nav.get(0).get("nav"),previous,nav.get(0).get("nav_date"),id,user);updated++;
        }else throw new IllegalStateException("SCHEME_CODE_REQUIRED");
      }catch(Exception ex){
        String reason=ex.getMessage();
        if(reason==null||reason.isBlank()||reason.length()>80)reason=ex.getClass().getSimpleName();
        skipped.add(Map.of("symbol",symbol,"reason",reason));
      }
    }
    Map<String,Object> out=new LinkedHashMap<>();out.put("updated",updated);out.put("history_synced",historySynced);
    out.put("total",rows.size());out.put("skipped",skipped);out.put("refreshed_at",java.time.Instant.now());
    return out;
  }
}
