package com.trading.api;

import com.trading.market.MarketCalendarService;
import java.math.*;
import java.time.*;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

/** Private saved goals; balances are explicitly earmarked, never inferred from holdings. */
@RestController
@RequestMapping("/api/v1/portfolio/goals")
public class PortfolioGoalController {
  private final JdbcTemplate jdbc;
  public PortfolioGoalController(JdbcTemplate jdbc){this.jdbc=jdbc;}
  public record Input(String name,BigDecimal targetAmount,BigDecimal reservedAmount,LocalDate balanceDate,
    LocalDate deadline,BigDecimal monthlyContribution){}
  record Progress(String status,int remainingMonthEnds,BigDecimal recordedProgressPercent,
    BigDecimal recordedGap,BigDecimal zeroGrowthProjectedBalance,BigDecimal zeroGrowthShortfall,
    BigDecimal requiredMonthlyContribution,BigDecimal additionalMonthlyContribution){}
  record Goal(UUID id,String name,BigDecimal targetAmount,BigDecimal reservedAmount,LocalDate balanceDate,
    LocalDate deadline,BigDecimal monthlyContribution,Progress progress){}
  @GetMapping
  public Map<String,Object> goals(){
    UUID owner=AuthSecurity.currentUser();
    LocalDate today=LocalDate.now(MarketCalendarService.IST);
    List<Goal> goals=jdbc.query("""
      SELECT id,name,target_amount,reserved_amount,balance_date,deadline,monthly_contribution
      FROM portfolio_saved_goals WHERE user_id=? ORDER BY deadline,id
      """,(rs,row)->{
        var input=new Input(rs.getString("name"),rs.getBigDecimal("target_amount"),rs.getBigDecimal("reserved_amount"),
          rs.getObject("balance_date",LocalDate.class),rs.getObject("deadline",LocalDate.class),rs.getBigDecimal("monthly_contribution"));
        return new Goal(rs.getObject("id",UUID.class),input.name(),input.targetAmount(),input.reservedAmount(),
          input.balanceDate(),input.deadline(),input.monthlyContribution(),progress(input,today));
      },owner);
    return Map.of("as_of",today.toString(),"goals",goals,"notice",
      "Recorded earmarked balances only; never assumes all portfolio holdings are available. Zero-growth funding arithmetic assumes unchanged reserved balance and contributions at future calendar month ends through the deadline. No contribution is presumed paid. Update recorded balances after actual changes. Balances older than 30 calendar days withhold forward estimates. No return forecast, taxes, fees, inflation, liquidity or affordability assessment. Keep balances distinct across goals; no automatic portfolio assignment or bank connection.");
  }
  @PostMapping
  public Map<String,Object> create(@RequestBody Input input){
    UUID owner=AuthSecurity.currentUser();validate(input,LocalDate.now(MarketCalendarService.IST));
    UUID id=UUID.randomUUID();
    int count=jdbc.update("""
      INSERT INTO portfolio_saved_goals(id,user_id,slot,name,target_amount,reserved_amount,balance_date,deadline,monthly_contribution)
      SELECT ?,?,candidate,?,?,?,?,?,? FROM generate_series(1,10) AS slots(candidate)
      WHERE NOT EXISTS(SELECT 1 FROM portfolio_saved_goals WHERE user_id=? AND slot=candidate)
      ORDER BY candidate LIMIT 1 ON CONFLICT (user_id,slot) DO NOTHING
      """,id,owner,input.name().strip(),input.targetAmount(),input.reservedAmount(),input.balanceDate(),input.deadline(),input.monthlyContribution(),owner);
    if(count!=1)throw new ResponseStatusException(HttpStatus.CONFLICT,"Goal limit reached or concurrent change; refresh and retry");
    return Map.of("id",id,"saved",true);
  }
  @PutMapping("/{id}")
  public Map<String,Object> update(@PathVariable UUID id,@RequestBody Input input){
    UUID owner=AuthSecurity.currentUser();validate(input,LocalDate.now(MarketCalendarService.IST));
    if(jdbc.update("""
      UPDATE portfolio_saved_goals SET name=?,target_amount=?,reserved_amount=?,balance_date=?,deadline=?,
        monthly_contribution=?,updated_at=clock_timestamp() WHERE id=? AND user_id=?
      """,input.name().strip(),input.targetAmount(),input.reservedAmount(),input.balanceDate(),input.deadline(),input.monthlyContribution(),id,owner)!=1)
      throw new ResponseStatusException(HttpStatus.NOT_FOUND);
    return Map.of("id",id,"saved",true);
  }
  @DeleteMapping("/{id}")
  public Map<String,Boolean> delete(@PathVariable UUID id){
    if(jdbc.update("DELETE FROM portfolio_saved_goals WHERE id=? AND user_id=?",id,AuthSecurity.currentUser())!=1)
      throw new ResponseStatusException(HttpStatus.NOT_FOUND);
    return Map.of("deleted",true);
  }
  static void validate(Input input,LocalDate today){
    if(input==null||input.name()==null||input.name().isBlank()||input.name().strip().length()>80||
        input.name().codePoints().anyMatch(Character::isISOControl)||
        !amount(input.targetAmount(),1000000000L,true)||!amount(input.reservedAmount(),1000000000L,false)||
        !amount(input.monthlyContribution(),10000000L,false)||
        input.balanceDate()==null||input.balanceDate().isBefore(LocalDate.of(1970,1,1))||input.balanceDate().isAfter(today)||
        input.deadline()==null||input.deadline().isBefore(LocalDate.of(1970,1,1))||input.deadline().isAfter(today.plusYears(50)))
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid goal name, amount, balance date or deadline");
  }
  private static boolean amount(BigDecimal n,long max,boolean positive){
    return n!=null&&n.signum()>=(positive?1:0)&&n.compareTo(BigDecimal.valueOf(max))<=0&&n.stripTrailingZeros().scale()<=2;
  }
  static Progress progress(Input input,LocalDate today){
    int months=0;
    for(YearMonth m=YearMonth.from(today);!m.atEndOfMonth().isAfter(input.deadline());m=m.plusMonths(1))
      if(m.atEndOfMonth().isAfter(today))months++;
    BigDecimal gap=input.targetAmount().subtract(input.reservedAmount()).max(BigDecimal.ZERO);
    BigDecimal pct=input.reservedAmount().multiply(BigDecimal.valueOf(100)).divide(input.targetAmount(),2,RoundingMode.HALF_UP);
    if(input.balanceDate().isBefore(today.minusDays(30))||input.balanceDate().isAfter(today))
      return new Progress("STALE_RECORDED_BALANCE",months,pct,gap,null,null,null,null);
    BigDecimal projected=input.reservedAmount().add(input.monthlyContribution().multiply(BigDecimal.valueOf(months)));
    BigDecimal shortfall=input.targetAmount().subtract(projected).max(BigDecimal.ZERO);
    BigDecimal required=months==0?null:gap.divide(BigDecimal.valueOf(months),2,RoundingMode.CEILING);
    BigDecimal additional=required==null?null:required.subtract(input.monthlyContribution()).max(BigDecimal.ZERO);
    String status=gap.signum()==0?"RECORDED_TARGET_FUNDED":
      months==0?"NO_REMAINING_MONTH_ENDS":shortfall.signum()==0?"FUNDED_UNDER_ZERO_GROWTH":"FUNDING_SHORTFALL";
    return new Progress(status,months,pct,gap,projected,shortfall,required,additional);
  }
}
