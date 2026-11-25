package com.trading.market;

import java.math.*;
import java.util.*;

/** Exact-identity concentration arithmetic, never an order, allocation target or forecast. */
final class PortfolioAllocationResearch {
  private PortfolioAllocationResearch(){}
  private static final BigDecimal SINGLE=new BigDecimal("0.25"),TOP=new BigDecimal("0.60");
  private static final BigDecimal HUNDRED=BigDecimal.valueOf(100);
  private static final MathContext MC=MathContext.DECIMAL128;
  record Scenario(int hypotheticalNewIdentities,BigDecimal additionalCapital,
      BigDecimal equalNewInvestmentAmount,BigDecimal projectedLargestPercent,BigDecimal projectedTopThreePercent,
      BigDecimal hypotheticalRedistributedCapital,BigDecimal redistributedPercent){}

  static Map<String,Object> assess(List<BigDecimal> values,BigDecimal total,boolean complete){
    var result=new LinkedHashMap<String,Object>();
    result.put("notice","Illustrative concentration arithmetic only, using recent recorded values. New identities are hypothetical distinct investments, not selected securities or funds. Prices are held constant. Fixed-capital redistribution assumes a proportional reduction of every existing identity before fees, taxes, exit loads and execution constraints. Fund look-through, risk/return suitability and available capital are not established.");
    result.put("single_identity_review_threshold_percent",25);
    result.put("top_three_review_threshold_percent",60);
    result.put("scenarios",List.of());
    if(!complete||values.isEmpty()||total==null||total.signum()<=0||
        values.stream().anyMatch(v->v==null||v.signum()<=0||!Double.isFinite(v.doubleValue()))||
        values.stream().reduce(BigDecimal.ZERO,BigDecimal::add).compareTo(total)!=0){
      result.put("status","INSUFFICIENT_RECENT_EXACT_VALUATIONS");
      return result;
    }
    var ordered=values.stream().sorted(Comparator.reverseOrder()).toList();
    BigDecimal largest=ordered.getFirst(),topThree=top(ordered,3);
    result.put("recorded_value",total);
    result.put("current_largest_percent",percent(largest,total));
    result.put("current_top_three_percent",percent(topThree,total));
    if(largest.compareTo(total.multiply(SINGLE))<=0&&topThree.compareTo(total.multiply(TOP))<=0){
      result.put("status","WITHIN_ILLUSTRATIVE_CONCENTRATION_LIMITS");
      return result;
    }
    result.put("status","HYPOTHETICAL_SCENARIOS_AVAILABLE");
    var scenarios=List.of(scenario(ordered,total,5),scenario(ordered,total,10));
    result.put("scenarios",scenarios);
    List<PortfolioRebalancingCosts.Case> costs=new ArrayList<>();
    for(Scenario s:scenarios){
      String count=s.hypotheticalNewIdentities()+" new identities";
      costs.add(new PortfolioRebalancingCosts.Case(count+" · no-sale contribution",s.additionalCapital(),BigDecimal.ZERO));
      costs.add(new PortfolioRebalancingCosts.Case(count+" · fixed-capital redistribution",
        s.hypotheticalRedistributedCapital(),s.hypotheticalRedistributedCapital()));
    }
    result.put("cost_sensitivity",PortfolioRebalancingCosts.assess(total,costs));
    return result;
  }

  private static Scenario scenario(List<BigDecimal> values,BigDecimal total,int count){
    BigDecimal n=BigDecimal.valueOf(count);
    // x is the equal contribution to each new identity. For every possible
    // composition of the largest three, enforce its linear inequality exactly.
    BigDecimal x=required(values.getFirst().subtract(total.multiply(SINGLE)),SINGLE.multiply(n));
    for(int j=0;j<=3;j++){
      BigDecimal coefficient=TOP.multiply(n).subtract(BigDecimal.valueOf(j));
      BigDecimal excess=top(values,3-j).subtract(total.multiply(TOP));
      if(coefficient.signum()>0)x=x.max(required(excess,coefficient));
      else if(excess.signum()>0)throw new IllegalStateException("Infeasible illustrative scenario");
    }
    BigDecimal additional=x.multiply(n),future=total.add(additional);
    var after=new ArrayList<>(values);
    for(int i=0;i<count;i++)after.add(x);
    after.sort(Comparator.reverseOrder());
    // The proportional fixed-capital scenario has the same weights, without
    // requiring new capital; its rupee amount is an estimate, not executable.
    BigDecimal fraction=additional.divide(future,MC);
    return new Scenario(count,additional,x,percent(after.getFirst(),future),percent(top(after,3),future),
      total.multiply(fraction,MC).setScale(2,RoundingMode.HALF_UP),fraction.multiply(HUNDRED).setScale(2,RoundingMode.HALF_UP));
  }
  private static BigDecimal required(BigDecimal excess,BigDecimal coefficient){
    return excess.signum()<=0?BigDecimal.ZERO.setScale(2):excess.divide(coefficient,2,RoundingMode.CEILING);
  }
  private static BigDecimal top(List<BigDecimal> sorted,int count){
    return sorted.stream().limit(count).reduce(BigDecimal.ZERO,BigDecimal::add);
  }
  private static BigDecimal percent(BigDecimal value,BigDecimal total){
    return value.multiply(HUNDRED).divide(total,2,RoundingMode.HALF_UP);
  }
}
