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
    LocalDate deadline,BigDecimal monthlyContribution,Progress progress,Funding funding){}
  record LinkedHolding(long holdingId,String symbol,String assetType,String status,BigDecimal recordedValue){}
  record AvailableHolding(long holdingId,String symbol,String assetType){}
  record Funding(String status,BigDecimal linkedValue,BigDecimal totalRecordedFunding,List<LinkedHolding> holdings){}
  public record Assignment(boolean confirmSeparateBalance){}
  @GetMapping
  @org.springframework.transaction.annotation.Transactional(readOnly=true,isolation=org.springframework.transaction.annotation.Isolation.REPEATABLE_READ)
  public Map<String,Object> goals(){
    UUID owner=AuthSecurity.currentUser();
    LocalDate today=LocalDate.now(MarketCalendarService.IST);
    var linked=new HashMap<UUID,List<LinkedHolding>>();
    jdbc.query("""
      SELECT a.goal_id,a.holding_id,a.symbol,a.asset_type,
        CASE WHEN p.id IS NULL THEN 'MISSING_HOLDING'
          WHEN p.quantity<=0 OR p.last_price IS NULL OR p.last_price<0 OR p.price_as_of IS NULL
            OR p.price_as_of>now() OR (now() AT TIME ZONE 'Asia/Kolkata')::date-
              (p.price_as_of AT TIME ZONE 'Asia/Kolkata')::date >
              CASE WHEN p.asset_type='MUTUAL_FUND' THEN 7 ELSE 5 END THEN 'UNAVAILABLE_RECENT_VALUE'
          ELSE 'RECENT_RECORDED' END AS status,
        p.quantity*p.last_price AS recorded_value
      FROM portfolio_goal_holdings a LEFT JOIN personal_holdings p
        ON p.id=a.holding_id AND p.user_id=a.user_id AND p.symbol=a.symbol AND p.asset_type=a.asset_type
      WHERE a.user_id=? ORDER BY a.holding_id
      """,rs->{
        String status=rs.getString("status");
        linked.computeIfAbsent(rs.getObject("goal_id",UUID.class),k->new ArrayList<>()).add(
          new LinkedHolding(rs.getLong("holding_id"),rs.getString("symbol"),rs.getString("asset_type"),status,
            "RECENT_RECORDED".equals(status)?rs.getBigDecimal("recorded_value"):null));
      },owner);
    var available=jdbc.query("""
      SELECT p.id,p.symbol,p.asset_type FROM personal_holdings p
      WHERE p.user_id=? AND p.asset_type IN ('EQUITY','MUTUAL_FUND')
        AND NOT EXISTS(SELECT 1 FROM portfolio_goal_holdings a WHERE a.user_id=p.user_id AND a.holding_id=p.id)
      ORDER BY p.symbol,p.id LIMIT 200
      """,(rs,row)->new AvailableHolding(rs.getLong("id"),rs.getString("symbol"),rs.getString("asset_type")),owner);
    List<Goal> goals=jdbc.query("""
      SELECT id,name,target_amount,reserved_amount,balance_date,deadline,monthly_contribution
      FROM portfolio_saved_goals WHERE user_id=? ORDER BY deadline,id
      """,(rs,row)->{
        var input=new Input(rs.getString("name"),rs.getBigDecimal("target_amount"),rs.getBigDecimal("reserved_amount"),
          rs.getObject("balance_date",LocalDate.class),rs.getObject("deadline",LocalDate.class),rs.getBigDecimal("monthly_contribution"));
        UUID id=rs.getObject("id",UUID.class);
        var funding=funding(input,linked.getOrDefault(id,List.of()));
        return new Goal(id,input.name(),input.targetAmount(),input.reservedAmount(),
          input.balanceDate(),input.deadline(),input.monthlyContribution(),linkedProgress(input,funding,today),funding);
      },owner);
    return Map.of("as_of",today.toString(),"goals",goals,"availableHoldings",available,"notice",
      "Recorded earmarked savings plus explicitly assigned whole holdings only. Reserved savings must exclude assigned investment values and other goals. Recent recorded prices are not verified live or liquidation values. Missing/stale assigned holdings withhold total progress and projections. Zero-growth assumes unchanged values and future month-end contributions through the deadline. No contribution presumed paid. Balances older than 30 days withhold forward estimates. No return forecast, taxes, fees, inflation, liquidity, affordability or bank connection.");
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
  @PostMapping("/{id}/holdings/{holdingId}")
  @org.springframework.transaction.annotation.Transactional
  public Map<String,Boolean> assign(@PathVariable UUID id,@PathVariable long holdingId,@RequestBody Assignment input){
    UUID owner=AuthSecurity.currentUser();
    if(input==null||!input.confirmSeparateBalance()||holdingId<=0)
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Confirm that reserved savings exclude assigned holdings");
    // Serialize assignment changes for this owner, with the database uniqueness constraint as final protection.
    jdbc.queryForObject("SELECT id FROM atlas_users WHERE id=? FOR UPDATE",UUID.class,owner);
    if(jdbc.queryForList("SELECT id FROM portfolio_saved_goals WHERE user_id=? AND id=? FOR UPDATE",UUID.class,owner,id).isEmpty())
      throw new ResponseStatusException(HttpStatus.NOT_FOUND);
    if(jdbc.queryForList("SELECT id FROM personal_holdings WHERE user_id=? AND id=? AND asset_type IN ('EQUITY','MUTUAL_FUND') FOR UPDATE",
        Long.class,owner,holdingId).isEmpty())throw new ResponseStatusException(HttpStatus.NOT_FOUND);
    if(jdbc.queryForObject("SELECT count(*) FROM portfolio_goal_holdings WHERE user_id=?",Integer.class,owner)>=100)
      throw new ResponseStatusException(HttpStatus.CONFLICT,"Assignment limit reached");
    if(jdbc.update("""
      INSERT INTO portfolio_goal_holdings(user_id,goal_id,holding_id,symbol,asset_type)
      SELECT user_id,?,id,symbol,asset_type FROM personal_holdings WHERE user_id=? AND id=?
      ON CONFLICT (user_id,holding_id) DO NOTHING
      """,id,owner,holdingId)!=1)throw new ResponseStatusException(HttpStatus.CONFLICT,"Holding is already assigned");
    return Map.of("assigned",true);
  }
  @DeleteMapping("/{id}/holdings/{holdingId}")
  public Map<String,Boolean> unassign(@PathVariable UUID id,@PathVariable long holdingId){
    if(jdbc.update("DELETE FROM portfolio_goal_holdings WHERE user_id=? AND goal_id=? AND holding_id=?",
        AuthSecurity.currentUser(),id,holdingId)!=1)throw new ResponseStatusException(HttpStatus.NOT_FOUND);
    return Map.of("removed",true);
  }
  static Funding funding(Input input,List<LinkedHolding> holdings){
    if(holdings.stream().anyMatch(h->!"RECENT_RECORDED".equals(h.status())||h.recordedValue()==null||
        h.recordedValue().signum()<0||!Double.isFinite(h.recordedValue().doubleValue())))
      return new Funding("INCOMPLETE_LINKED_VALUATION",null,null,List.copyOf(holdings));
    BigDecimal value=holdings.stream().map(LinkedHolding::recordedValue).reduce(BigDecimal.ZERO,BigDecimal::add);
    return new Funding(holdings.isEmpty()?"NO_LINKED_HOLDINGS":"RECENT_RECORDED_LINKED_VALUE",value,
      input.reservedAmount().add(value),List.copyOf(holdings));
  }
  static Progress linkedProgress(Input input,Funding funding,LocalDate today){
    if(funding.totalRecordedFunding()==null){
      var base=progress(input,today);
      return new Progress("INCOMPLETE_LINKED_VALUATION",base.remainingMonthEnds(),null,null,null,null,null,null);
    }
    return progress(new Input(input.name(),input.targetAmount(),funding.totalRecordedFunding(),input.balanceDate(),
      input.deadline(),input.monthlyContribution()),today);
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
