package com.trading.api;

import java.math.*;
import java.time.LocalDate;
import com.trading.market.MarketCalendarService;
import com.trading.market.PortfolioFlowAdjustedPerformance;
import com.trading.market.PortfolioRollingPerformance;
import com.trading.market.PortfolioBenchmarkEvidence;
import com.trading.market.PortfolioBenchmarkRisk;
import java.time.temporal.ChronoUnit;
import java.util.*;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/v1/portfolio/history")
public class PortfolioHistoryController {
  private final JdbcTemplate jdbc;
  public PortfolioHistoryController(JdbcTemplate jdbc){this.jdbc=jdbc;}

  public record TransactionInput(String symbol,String assetType,String transactionType,LocalDate transactionDate,
                                 BigDecimal quantity,BigDecimal unitPrice,BigDecimal cashAmount,
                                 String sourceCode,String sourceReference,String notes){}
  private record CashFlow(LocalDate date,double amount){}

  @GetMapping("/transactions")
  public List<Map<String,Object>> transactions(){
    return jdbc.queryForList("""
      SELECT id,symbol,asset_type,transaction_type,transaction_date,quantity,unit_price,cash_amount,
      source_code,source_reference,notes,created_at FROM portfolio_transactions
      WHERE user_id=? ORDER BY transaction_date,id
      """,AuthSecurity.currentUser());
  }
  @PostMapping("/transactions")
  public Map<String,Object> saveTransaction(@RequestBody TransactionInput input){
    if(input==null||input.symbol()==null||!input.symbol().trim().matches("[A-Za-z0-9._&-]{1,50}"))bad("Invalid symbol");
    String asset=upper(input.assetType()),type=upper(input.transactionType());
    if(!Set.of("EQUITY","MUTUAL_FUND","CASH").contains(asset))bad("Invalid asset type");
    if(!Set.of("BUY","SELL","DIVIDEND","FEE","DEPOSIT","WITHDRAWAL").contains(type))bad("Invalid transaction type");
    if(input.transactionDate()==null||input.transactionDate().isAfter(LocalDate.now(MarketCalendarService.IST))||input.transactionDate().isBefore(LocalDate.of(1970,1,1)))bad("Invalid transaction date");
    if(input.cashAmount()==null||input.cashAmount().signum()<=0)bad("Cash amount must be positive");
    if(input.quantity()!=null&&input.quantity().signum()<=0)bad("Quantity must be positive");
    if(input.unitPrice()!=null&&input.unitPrice().signum()<0)bad("Unit price cannot be negative");
    if(Set.of("BUY","SELL").contains(type)&&(input.quantity()==null||input.unitPrice()==null))bad("Buy and sell transactions require quantity and unit price");
    String source=input.sourceCode()==null||input.sourceCode().isBlank()?"MANUAL":input.sourceCode().trim().toUpperCase(Locale.ROOT);
    if(!source.matches("[A-Z0-9_.-]{1,60}"))bad("Invalid source code");
    if(input.sourceReference()!=null&&input.sourceReference().length()>180)bad("Source reference too long");
    if(input.notes()!=null&&input.notes().length()>500)bad("Notes too long");
    UUID id=jdbc.queryForObject("""
      INSERT INTO portfolio_transactions(user_id,symbol,asset_type,transaction_type,transaction_date,
      quantity,unit_price,cash_amount,source_code,source_reference,notes)
      VALUES (?,?,?,?,?,?,?,?,?,?,?) RETURNING id
      """,UUID.class,AuthSecurity.currentUser(),input.symbol().trim().toUpperCase(Locale.ROOT),asset,type,
      input.transactionDate(),input.quantity(),input.unitPrice(),input.cashAmount(),source,input.sourceReference(),input.notes());
    return Map.of("saved",true,"id",id);
  }
  @DeleteMapping("/transactions/{id}")
  public Map<String,Boolean> deleteTransaction(@PathVariable UUID id){
    if(jdbc.update("DELETE FROM portfolio_transactions WHERE id=? AND user_id=?",id,AuthSecurity.currentUser())==0)
      throw new ResponseStatusException(HttpStatus.NOT_FOUND);
    return Map.of("deleted",true);
  }

  @PostMapping("/snapshots/current")
  public Map<String,Object> snapshot(){
    UUID user=AuthSecurity.currentUser();
    Map<String,Object> totals=jdbc.queryForMap("""
      SELECT COALESCE(sum(quantity*last_price) FILTER(WHERE last_price IS NOT NULL),0) total_value,
      count(*) FILTER(WHERE last_price IS NOT NULL) priced,
      count(*) FILTER(WHERE last_price IS NULL) unpriced,
      min(price_as_of) oldest_price_at,max(price_as_of) newest_price_at,
      count(*) FILTER(WHERE last_price IS NOT NULL AND
        (price_as_of IS NULL OR price_as_of>now() OR
          (now() AT TIME ZONE 'Asia/Kolkata')::date-(price_as_of AT TIME ZONE 'Asia/Kolkata')::date>
            CASE WHEN asset_type='MUTUAL_FUND' THEN 7 ELSE 5 END)) aged_or_undated
      FROM personal_holdings WHERE user_id=?
      """,user);
    LocalDate date=LocalDate.now(MarketCalendarService.IST);
    if(((Number)totals.get("priced")).longValue()==0||((Number)totals.get("unpriced")).longValue()>0||
        ((Number)totals.get("aged_or_undated")).longValue()>0){
      Map<String,Object> result=new LinkedHashMap<>(totals);result.put("valuation_date",date);
      result.put("recorded",false);result.put("reason","INCOMPLETE_OR_AGED_RECORDED_VALUATION");
      return result;
    }
    jdbc.update("""
      INSERT INTO portfolio_valuation_snapshots(user_id,valuation_date,total_value,priced_positions,unpriced_positions,
        capture_source,oldest_price_at,newest_price_at)
      VALUES (?,?,?,?,?,'MANUAL_RECORDED',?,?) ON CONFLICT(user_id,valuation_date) DO UPDATE SET total_value=EXCLUDED.total_value,
      priced_positions=EXCLUDED.priced_positions,unpriced_positions=EXCLUDED.unpriced_positions,created_at=now(),
      capture_source=EXCLUDED.capture_source,oldest_price_at=EXCLUDED.oldest_price_at,newest_price_at=EXCLUDED.newest_price_at
      """,user,date,totals.get("total_value"),totals.get("priced"),totals.get("unpriced"),totals.get("oldest_price_at"),totals.get("newest_price_at"));
    Map<String,Object> result=new LinkedHashMap<>(totals);result.put("valuation_date",date);result.put("recorded",true);return result;
  }

  @GetMapping("/performance")
  public Map<String,Object> performance(){
    UUID user=AuthSecurity.currentUser();
    List<Map<String,Object>> snapshots=jdbc.queryForList("SELECT valuation_date,total_value,priced_positions,unpriced_positions,capture_source,oldest_price_at,newest_price_at FROM portfolio_valuation_snapshots WHERE user_id=? ORDER BY valuation_date",user);
    List<Map<String,Object>> transactions=jdbc.queryForList("SELECT transaction_date,transaction_type,cash_amount FROM portfolio_transactions WHERE user_id=? ORDER BY transaction_date",user);
    LocalDate today=LocalDate.now(MarketCalendarService.IST);
    List<Map<String,Object>> dated=snapshots.stream().filter(row->!day(row.get("valuation_date")).isAfter(today)).toList();
    Map<String,Object> last=dated.isEmpty()?null:dated.get(dated.size()-1);
    LocalDate terminal=last==null?null:day(last.get("valuation_date"));
    LocalDate firstSnapshot=dated.isEmpty()?null:day(dated.get(0).get("valuation_date"));
    int incomplete=(int)dated.stream().filter(row->!complete(row)).count();
    int afterTerminal=0,externalCount=0;
    boolean interveningFlow=false;
    List<CashFlow> flows=new ArrayList<>();
    List<PortfolioFlowAdjustedPerformance.Flow> adjustmentFlows=new ArrayList<>();
    for(Map<String,Object> row:transactions){
      String type=(String)row.get("transaction_type");
      // DIVIDEND and FEE represent explicitly external cash flows in the
      // existing ledger contract; internal reinvestments are not external.
      if(!Set.of("DEPOSIT","WITHDRAWAL","DIVIDEND","FEE").contains(type))continue;
      LocalDate date=day(row.get("transaction_date"));
      if(terminal==null||date.isAfter(terminal)){afterTerminal++;continue;}
      BigDecimal cash=(BigDecimal)row.get("cash_amount");
      if("DEPOSIT".equals(type)||"FEE".equals(type))cash=cash.negate();
      flows.add(new CashFlow(date,cash.doubleValue()));externalCount++;
      adjustmentFlows.add(new PortfolioFlowAdjustedPerformance.Flow(date,cash.negate()));
      if(firstSnapshot!=null&&date.isAfter(firstSnapshot))interveningFlow=true;
    }
    String xirrStatus="UNAVAILABLE_REQUIRES_EXTERNAL_CASH_FLOWS_AND_VALUATION";
    Double xirr=null;
    if(last!=null&&!complete(last))xirrStatus="UNAVAILABLE_INCOMPLETE_TERMINAL_VALUATION";
    else if(last!=null&&externalCount>0){
      flows.add(new CashFlow(terminal,((BigDecimal)last.get("total_value")).doubleValue()));
      xirr=xirr(flows);
      xirrStatus=xirr==null?"UNAVAILABLE_AMBIGUOUS_OR_UNSUPPORTED_CASH_FLOWS":"AVAILABLE";
    }
    // Raw valuation drawdown is not investment drawdown when external cash
    // moves within the observation window. Do not bridge incomplete records.
    Double drawdown=null;
    String drawdownStatus="UNAVAILABLE_REQUIRES_TWO_VALUATION_DATES";
    if(dated.size()>=2){
      if(incomplete>0)drawdownStatus="UNAVAILABLE_INCOMPLETE_VALUATION_HISTORY";
      else if(interveningFlow)drawdownStatus="UNAVAILABLE_EXTERNAL_FLOWS_REQUIRE_FLOW_ADJUSTED_HISTORY";
      else {
        drawdown=maxDrawdown(dated);
        drawdownStatus=drawdown==null?"UNAVAILABLE_INVALID_VALUATION_HISTORY":"AVAILABLE";
      }
    }
    var observations=dated.stream()
      .map(row->new PortfolioFlowAdjustedPerformance.Observation(day(row.get("valuation_date")),
        (BigDecimal)row.get("total_value"),complete(row))).toList();
    var adjusted=PortfolioFlowAdjustedPerformance.calculate(observations,adjustmentFlows);
    var benchmark=terminal==null?List.<PortfolioRollingPerformance.BenchmarkPoint>of():PortfolioBenchmarkEvidence.points(jdbc,terminal,today);
    var rolling=PortfolioRollingPerformance.windows(observations,adjustmentFlows,benchmark);
    var risk=PortfolioRollingPerformance.risk(observations,adjustmentFlows);
    Map<String,Object> result=new LinkedHashMap<>();
    result.put("rolling_performance",rolling);
    result.put("weekly_risk_estimate",risk);
    result.put("benchmark_risk_estimate",PortfolioBenchmarkRisk.assess(observations,adjustmentFlows,benchmark,today));
    result.put("benchmark_reference","NIFTY 50 price index (not TRI)");
    var eligibleBenchmark=benchmark.stream().filter(PortfolioRollingPerformance.BenchmarkPoint::eligible).toList();
    result.put("benchmark_eligible_observation_count",eligibleBenchmark.stream().map(PortfolioRollingPerformance.BenchmarkPoint::date).distinct().count());
    result.put("benchmark_latest_eligible_date",eligibleBenchmark.stream().map(PortfolioRollingPerformance.BenchmarkPoint::date).max(LocalDate::compareTo).map(LocalDate::toString).orElse(null));
    result.put("benchmark_history_status",terminal==null?"NO_PORTFOLIO_WINDOW":eligibleBenchmark.isEmpty()?"NO_ELIGIBLE_STORED_OBSERVATIONS":"STORED_OBSERVATIONS_AVAILABLE");
    result.put("rolling_methodology","Exact trailing 30, 90 and 365 calendar-day recorded valuations through the latest saved date; no interpolation. Linked Dietz estimates retain all evidence gates. NIFTY 50 is a broad equity price reference, not a suitable blended benchmark for every portfolio. Comparisons require exact dates, one unambiguous NSE index registry identity, consistent enabled source and validated completed raw index candles mapped to stored regular-session closes. No dividend or total-return comparison, alpha or tracking error. Weekly risk requires thirteen exact seven-day intervals; sample volatility and downside deviation relative to zero are annualized with square root of 52. No risk-free rate or Sharpe/Sortino estimate is assumed.");
    result.put("flow_adjusted_status",adjusted.status());
    result.put("flow_adjusted_return_percent",adjusted.returnPercent()==null?null:BigDecimal.valueOf(adjusted.returnPercent()).setScale(4,RoundingMode.HALF_UP));
    result.put("flow_adjusted_drawdown_percent",adjusted.drawdownPercent()==null?null:BigDecimal.valueOf(adjusted.drawdownPercent()).setScale(4,RoundingMode.HALF_UP));
    result.put("flow_adjusted_interval_count",adjusted.intervals());
    result.put("flow_adjusted_cash_flow_count",adjusted.flowCount());
    result.put("flow_adjusted_max_interval_days",adjusted.maximumIntervalDays());
    result.put("flow_adjusted_from",adjusted.from());
    result.put("flow_adjusted_through",adjusted.through());
    result.put("flow_adjusted_methodology","Linked Modified Dietz estimate, not exact time-weighted return. Dated external flows are weighted by remaining calendar days; first-date flows are opening capital, end-date flows occur after returns. Intervals over seven days, incomplete valuations and invalid capital bases are withheld. Externally paid fees follow the existing negative investor-flow convention. Holdings-only valuations and recorded ledger flows may omit cash, fees and transactions. Drawdown uses the estimated wealth index at observation dates.");
    // Owner-scoped recorded observations; incomplete dates remain explicit gaps.
    result.put("valuation_history",dated.stream().map(row->{
      Map<String,Object> point=new LinkedHashMap<>();point.put("date",day(row.get("valuation_date")).toString());
      point.put("value",complete(row)?row.get("total_value"):null);return point;
    }).toList());
    result.put("transaction_count",transactions.size());result.put("snapshot_count",snapshots.size());
    result.put("external_cash_flow_count",externalCount);result.put("external_flows_after_valuation",afterTerminal);
    result.put("incomplete_snapshot_count",incomplete);result.put("future_snapshot_count",snapshots.size()-dated.size());
    result.put("valuation_through",terminal==null?null:terminal.toString());
    result.put("automatic_snapshot_count",dated.stream().filter(row->"AUTO_RECORDED".equals(row.get("capture_source"))).count());
    result.put("latest_capture_source",last==null?null:last.get("capture_source"));
    result.put("latest_oldest_price_at",last==null||last.get("oldest_price_at")==null?null:((java.sql.Timestamp)last.get("oldest_price_at")).toInstant().toString());
    result.put("latest_newest_price_at",last==null||last.get("newest_price_at")==null?null:((java.sql.Timestamp)last.get("newest_price_at")).toInstant().toString());
    result.put("xirr_percent",xirr==null?null:round(xirr*100));result.put("xirr_status",xirrStatus);
    result.put("maximum_drawdown_percent",drawdown==null?null:round(drawdown*100));result.put("drawdown_status",drawdownStatus);
    result.put("methodology","Recorded holdings-only valuations and explicitly external cash flows through the latest nonfuture valuation date. BUY and SELL are internal allocation changes. Drawdown is withheld for incomplete history or intervening external flows. Unrecorded cash, fees, dividends or transactions can invalidate results; recorded prices are not verified live values.");
    return result;
  }

  private static LocalDate day(Object value){
    return value instanceof java.sql.Date d?d.toLocalDate():(LocalDate)value;
  }
  private static boolean complete(Map<String,Object> row){
    return ((Number)row.get("priced_positions")).longValue()>0
      &&((Number)row.get("unpriced_positions")).longValue()==0
      &&row.get("total_value") instanceof BigDecimal value&&value.signum()>=0
      &&Double.isFinite(value.doubleValue());
  }

  static Double xirr(List<CashFlow> flows){
    // Net same-date flows before solving. A single negative-to-positive
    // transition provides a conservative unique-root condition.
    TreeMap<LocalDate,Double> daily=new TreeMap<>();
    for(CashFlow flow:flows){
      if(!Double.isFinite(flow.amount()))return null;
      daily.merge(flow.date(),flow.amount(),Double::sum);
    }
    List<CashFlow> net=new ArrayList<>();
    boolean positive=false;
    for(var entry:daily.entrySet()){
      double value=entry.getValue();
      if(!Double.isFinite(value))return null;
      if(value==0)continue;
      if(value>0)positive=true;
      else if(positive)return null;
      net.add(new CashFlow(entry.getKey(),value));
    }
    if(net.size()<2||net.get(0).amount()>=0||!positive)return null;
    flows=net;
    LocalDate first=net.get(0).date();
    double low=-0.9999,high=10.0,a=npv(flows,first,low),b=npv(flows,first,high);
    if(!Double.isFinite(a)||!Double.isFinite(b))return null;
    if(a==0)return low;if(b==0)return high;
    if(Math.signum(a)==Math.signum(b))return null;
    for(int i=0;i<160;i++){
      double mid=(low+high)/2,value=npv(flows,first,mid);
      if(!Double.isFinite(value))return null;
      if(Math.abs(value)<1e-8)return mid;
      if(Math.signum(value)==Math.signum(a)){low=mid;a=value;}else high=mid;
    }
    return (low+high)/2;
  }
  private static double npv(List<CashFlow> flows,LocalDate first,double rate){
    double total=0;for(CashFlow flow:flows){double years=ChronoUnit.DAYS.between(first,flow.date())/365.0;total+=flow.amount()/Math.pow(1+rate,years);}return total;
  }
  private static Double maxDrawdown(List<Map<String,Object>> snapshots){
    if(snapshots.size()<2||((BigDecimal)snapshots.get(0).get("total_value")).signum()<=0)return null;double peak=-1,drawdown=0;
    for(Map<String,Object> row:snapshots){double value=((BigDecimal)row.get("total_value")).doubleValue();peak=Math.max(peak,value);if(peak>0)drawdown=Math.min(drawdown,value/peak-1);}
    return drawdown;
  }
  private static double round(double value){return Math.round(value*10_000d)/10_000d;}
  private static String upper(String value){return value==null?"":value.trim().toUpperCase(Locale.ROOT);}
  private static void bad(String message){throw new ResponseStatusException(HttpStatus.BAD_REQUEST,message);}
}

