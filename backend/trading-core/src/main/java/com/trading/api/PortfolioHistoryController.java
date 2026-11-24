package com.trading.api;

import java.math.*;
import java.time.LocalDate;
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
    if(input.transactionDate()==null||input.transactionDate().isAfter(LocalDate.now())||input.transactionDate().isBefore(LocalDate.of(1970,1,1)))bad("Invalid transaction date");
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
      count(*) FILTER(WHERE last_price IS NULL) unpriced
      FROM personal_holdings WHERE user_id=?
      """,user);
    LocalDate date=LocalDate.now();
    jdbc.update("""
      INSERT INTO portfolio_valuation_snapshots(user_id,valuation_date,total_value,priced_positions,unpriced_positions)
      VALUES (?,?,?,?,?) ON CONFLICT(user_id,valuation_date) DO UPDATE SET total_value=EXCLUDED.total_value,
      priced_positions=EXCLUDED.priced_positions,unpriced_positions=EXCLUDED.unpriced_positions,created_at=now()
      """,user,date,totals.get("total_value"),totals.get("priced"),totals.get("unpriced"));
    Map<String,Object> result=new LinkedHashMap<>(totals);result.put("valuation_date",date);result.put("recorded",true);return result;
  }

  @GetMapping("/performance")
  public Map<String,Object> performance(){
    UUID user=AuthSecurity.currentUser();
    List<Map<String,Object>> snapshots=jdbc.queryForList("SELECT valuation_date,total_value,priced_positions,unpriced_positions FROM portfolio_valuation_snapshots WHERE user_id=? ORDER BY valuation_date",user);
    List<Map<String,Object>> transactions=jdbc.queryForList("SELECT transaction_date,transaction_type,cash_amount FROM portfolio_transactions WHERE user_id=? ORDER BY transaction_date",user);
    List<CashFlow> flows=new ArrayList<>();
    for(Map<String,Object> row:transactions){
      String type=(String)row.get("transaction_type");double cash=((BigDecimal)row.get("cash_amount")).doubleValue();
      // Only external portfolio cash flows belong in money-weighted return.
      // Security buys/sells are internal allocation changes and are excluded.
      if("DEPOSIT".equals(type)||"FEE".equals(type))cash=-cash;
      else if(!"WITHDRAWAL".equals(type)&&!"DIVIDEND".equals(type))continue;
      flows.add(new CashFlow(((java.sql.Date)row.get("transaction_date")).toLocalDate(),cash));
    }
    if(!snapshots.isEmpty()){
      Map<String,Object> last=snapshots.get(snapshots.size()-1);
      flows.add(new CashFlow(((java.sql.Date)last.get("valuation_date")).toLocalDate(),((BigDecimal)last.get("total_value")).doubleValue()));
    }
    Double xirr=xirr(flows),drawdown=maxDrawdown(snapshots);
    Map<String,Object> result=new LinkedHashMap<>();
    result.put("transaction_count",transactions.size());result.put("snapshot_count",snapshots.size());
    result.put("xirr_percent",xirr==null?null:round(xirr*100));
    result.put("xirr_status",xirr==null?"UNAVAILABLE_REQUIRES_EXTERNAL_CASH_FLOWS_AND_VALUATION":"AVAILABLE");
    result.put("maximum_drawdown_percent",drawdown==null?null:round(drawdown*100));
    result.put("drawdown_status",drawdown==null?"UNAVAILABLE_REQUIRES_TWO_VALUATION_DATES":"AVAILABLE");
    result.put("methodology","XIRR uses DEPOSIT, WITHDRAWAL, DIVIDEND and FEE cash flows plus the latest dated portfolio valuation. BUY and SELL are internal allocation changes. Drawdown uses recorded dated portfolio valuations.");
    return result;
  }

  static Double xirr(List<CashFlow> flows){
    if(flows.size()<2||flows.stream().noneMatch(f->f.amount<0)||flows.stream().noneMatch(f->f.amount>0))return null;
    LocalDate first=flows.stream().map(CashFlow::date).min(LocalDate::compareTo).orElseThrow();
    double low=-0.9999,high=10.0,a=npv(flows,first,low),b=npv(flows,first,high);
    if(!Double.isFinite(a)||!Double.isFinite(b)||Math.signum(a)==Math.signum(b))return null;
    for(int i=0;i<160;i++){
      double mid=(low+high)/2,value=npv(flows,first,mid);
      if(Math.abs(value)<1e-8)return mid;
      if(Math.signum(value)==Math.signum(a)){low=mid;a=value;}else high=mid;
    }
    return (low+high)/2;
  }
  private static double npv(List<CashFlow> flows,LocalDate first,double rate){
    double total=0;for(CashFlow flow:flows){double years=ChronoUnit.DAYS.between(first,flow.date())/365.0;total+=flow.amount()/Math.pow(1+rate,years);}return total;
  }
  private static Double maxDrawdown(List<Map<String,Object>> snapshots){
    if(snapshots.size()<2)return null;double peak=-1,drawdown=0;
    for(Map<String,Object> row:snapshots){double value=((BigDecimal)row.get("total_value")).doubleValue();peak=Math.max(peak,value);if(peak>0)drawdown=Math.min(drawdown,value/peak-1);}
    return drawdown;
  }
  private static double round(double value){return Math.round(value*10_000d)/10_000d;}
  private static String upper(String value){return value==null?"":value.trim().toUpperCase(Locale.ROOT);}
  private static void bad(String message){throw new ResponseStatusException(HttpStatus.BAD_REQUEST,message);}
}

