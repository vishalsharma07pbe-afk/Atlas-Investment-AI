package com.trading.api;

import java.math.*;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.*;
import static com.trading.api.PortfolioGoalController.*;

/** Goal-specific gross funding sensitivity, never a redemption recommendation. */
final class PortfolioGoalRisk {
  private PortfolioGoalRisk(){}
  private static final BigDecimal ZERO=BigDecimal.ZERO;
  record Scenario(String kind,int equityDeclinePercent,int fundDeclinePercent,BigDecimal hypotheticalLoss,
    BigDecimal stressedRecordedFunding,BigDecimal projectedFunding,BigDecimal projectedShortfall,
    BigDecimal requiredMonthlyContribution,BigDecimal additionalMonthlyContribution){}
  record Research(String status,long daysToDeadline,BigDecimal reservedSavings,BigDecimal equityValue,
    BigDecimal fundValue,BigDecimal grossWithdrawalGap,BigDecimal projectedWithdrawalGap,
    BigDecimal grossFundingNotCoveredByAssignedHoldings,BigDecimal recordedFundingSurplus,
    List<Scenario> scenarios,String reviewPriority,String notice){}
  static Research assess(Goal goal,LocalDate today){
    long days=ChronoUnit.DAYS.between(today,goal.deadline());
    String notice="Illustrative independent instantaneous shocks: direct equity -20%, fund NAV -10%, and both together. Reserved savings and future planned contributions are held unchanged; no contribution is assumed paid. Gross withdrawal gaps are arithmetic only, not available cash or executable redemptions. Actual liquidity, lock-ins, settlement, tax, exit loads, other charges and fund composition are not verified. No trades or automatic transfers.";
    var f=goal.funding();var p=goal.progress();
    if(f.totalRecordedFunding()==null||p.zeroGrowthProjectedBalance()==null||
       goal.balanceDate().isBefore(today.minusDays(30))||goal.balanceDate().isAfter(today))
      return new Research("INSUFFICIENT_FUNDING_EVIDENCE",days,goal.reservedAmount(),null,null,null,null,null,null,
        List.of(),"REVIEW_EVIDENCE",notice);
    BigDecimal equity=ZERO,funds=ZERO;
    for(var h:f.holdings()){
      if(h.recordedValue()==null||h.recordedValue().signum()<0||!"RECENT_RECORDED".equals(h.status()))
        return new Research("INSUFFICIENT_FUNDING_EVIDENCE",days,goal.reservedAmount(),null,null,null,null,null,null,List.of(),"REVIEW_EVIDENCE",notice);
      if("EQUITY".equals(h.assetType()))equity=equity.add(h.recordedValue());
      else if("MUTUAL_FUND".equals(h.assetType()))funds=funds.add(h.recordedValue());
      else return new Research("INSUFFICIENT_FUNDING_EVIDENCE",days,goal.reservedAmount(),null,null,null,null,null,null,List.of(),"REVIEW_EVIDENCE",notice);
    }
    if(equity.add(funds).add(goal.reservedAmount()).compareTo(f.totalRecordedFunding())!=0)
      return new Research("INSUFFICIENT_FUNDING_EVIDENCE",days,goal.reservedAmount(),null,null,null,null,null,null,List.of(),"REVIEW_EVIDENCE",notice);
    BigDecimal grossGap=goal.targetAmount().subtract(goal.reservedAmount()).max(ZERO);
    BigDecimal planned=goal.monthlyContribution().multiply(BigDecimal.valueOf(p.remainingMonthEnds()));
    BigDecimal futureGap=grossGap.subtract(planned).max(ZERO);
    BigDecimal uncovered=grossGap.subtract(equity).subtract(funds).max(ZERO);
    BigDecimal surplus=f.totalRecordedFunding().subtract(goal.targetAmount()).max(ZERO);
    List<Scenario> scenarios=new ArrayList<>();
    if(equity.signum()>0)scenarios.add(scenario(goal,equity,funds,20,0,"EQUITY_DECLINE"));
    if(funds.signum()>0)scenarios.add(scenario(goal,equity,funds,0,10,"FUND_NAV_DECLINE"));
    if(equity.signum()>0&&funds.signum()>0)scenarios.add(scenario(goal,equity,funds,20,10,"COMBINED_DECLINE"));
    boolean downsideGap=scenarios.stream().anyMatch(s->s.projectedShortfall().signum()>0);
    String priority=days<=90&&grossGap.signum()>0?"NEAR_DEADLINE_FUNDING_REVIEW":
      downsideGap?"DOWNSIDE_FUNDING_REVIEW":p.zeroGrowthShortfall().signum()>0?"BASELINE_FUNDING_REVIEW":"MONITOR";
    return new Research(scenarios.isEmpty()?"NO_POSITIVE_LINKED_EXPOSURE":"ILLUSTRATIVE_STRESS_AVAILABLE",days,
      money(goal.reservedAmount()),money(equity),money(funds),money(grossGap),money(futureGap),money(uncovered),money(surplus),
      List.copyOf(scenarios),priority,notice);
  }
  private static Scenario scenario(Goal g,BigDecimal equity,BigDecimal funds,int eq,int mf,String kind){
    BigDecimal loss=equity.multiply(BigDecimal.valueOf(eq)).movePointLeft(2).add(funds.multiply(BigDecimal.valueOf(mf)).movePointLeft(2));
    BigDecimal stressed=g.funding().totalRecordedFunding().subtract(loss);
    int months=g.progress().remainingMonthEnds();
    BigDecimal projected=stressed.add(g.monthlyContribution().multiply(BigDecimal.valueOf(months)));
    BigDecimal gap=g.targetAmount().subtract(stressed).max(ZERO);
    BigDecimal required=months==0?null:gap.divide(BigDecimal.valueOf(months),2,RoundingMode.CEILING);
    return new Scenario(kind,eq,mf,money(loss),money(stressed),money(projected),money(g.targetAmount().subtract(projected).max(ZERO)),
      required,required==null?null:required.subtract(g.monthlyContribution()).max(ZERO));
  }
  private static BigDecimal money(BigDecimal value){return value.setScale(2,RoundingMode.HALF_UP);}
}
