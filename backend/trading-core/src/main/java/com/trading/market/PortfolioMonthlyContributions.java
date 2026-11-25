package com.trading.market;

import java.math.*;
import java.util.*;

/** No-sale, constant-price monthly contribution illustrations, not selected investments. */
final class PortfolioMonthlyContributions {
  private PortfolioMonthlyContributions(){}
  private static final BigDecimal ZERO=BigDecimal.ZERO,HUNDRED=BigDecimal.valueOf(100);
  private static final List<Integer> HORIZONS=List.of(6,12,24,36);
  record Identity(String identity,String label,BigDecimal value){}
  record Addition(String identity,String label,BigDecimal monthlyAmount){}
  record Plan(String kind,int months,int hypotheticalNewIdentities,BigDecimal monthlyContribution,
      BigDecimal totalContribution,BigDecimal monthlyChargeAt50Bps,BigDecimal monthlyCashAt50Bps,
      BigDecimal midpointLargestPercent,BigDecimal midpointTopThreePercent,
      BigDecimal finalLargestPercent,BigDecimal finalTopThreePercent,boolean meetsIllustrativeLimits,
      List<Addition> allocations){}
  private record Concentration(BigDecimal largest,BigDecimal topThree,boolean within){}
  static Map<String,Object> assess(List<Identity> identities,BigDecimal total,Map<String,Object> allocation,boolean complete){
    var out=new LinkedHashMap<String,Object>();
    out.put("notice","Automatic no-sale monthly contribution illustrations at unchanged recorded prices, not an investment budget, SIP recommendation or return forecast. Existing identity top-ups are a mechanical equalization alternative, not an optimal allocation or a quality screen. New identities are hypothetical, not selected securities. Contributions are rounded upward per identity per month; actual minimum orders, fund overlap, asset suitability, taxes and execution constraints are not established. The 50 bps purchase-only charge is an illustrative separate cash requirement, not a broker or fund tariff. No recurring order is placed.");
    out.put("plans",List.of());
    if(!complete||total==null||total.signum()<=0||identities.isEmpty()||
        identities.size()>100||identities.stream().anyMatch(i->i.value()==null||i.value().signum()<=0||
          !Double.isFinite(i.value().doubleValue()))||
        identities.stream().map(Identity::identity).distinct().count()!=identities.size()||
        identities.stream().map(Identity::value).reduce(ZERO,BigDecimal::add).compareTo(total)!=0){
      out.put("status","INSUFFICIENT_RECENT_EXACT_VALUATIONS");return out;
    }
    var base=identities.stream().map(Identity::value).toList();
    if(concentration(base).within()){
      out.put("status","WITHIN_ILLUSTRATIVE_LIMITS");return out;
    }
    if(!"HYPOTHETICAL_SCENARIOS_AVAILABLE".equals(allocation.get("status"))||
        !(allocation.get("scenarios") instanceof List<?> scenarios)){
      out.put("status","INSUFFICIENT_ALLOCATION_EVIDENCE");return out;
    }
    List<Plan> plans=new ArrayList<>();
    // Five or more identities are necessary for a top-three limit of 60%.
    // Equalizing existing values avoids introducing invented securities.
    if(identities.size()>=5){
      BigDecimal largest=base.stream().max(BigDecimal::compareTo).orElseThrow();
      for(int months:HORIZONS){
        List<Addition> additions=identities.stream().map(i->new Addition(i.identity(),i.label(),
          monthly(largest.subtract(i.value()),months))).filter(a->a.monthlyAmount().signum()>0).toList();
        plans.add(plan("EXISTING_IDENTITY_EQUALIZATION",months,0,identities,additions));
      }
    }
    for(Object scenario:scenarios)if(scenario instanceof PortfolioAllocationResearch.Scenario s){
      int count=s.hypotheticalNewIdentities();
      if(count!=5&&count!=10)continue;
      for(int months:HORIZONS){
        BigDecimal amount=monthly(s.equalNewInvestmentAmount(),months);
        List<Addition> additions=new ArrayList<>();
        for(int i=1;i<=count;i++)additions.add(new Addition("HYPOTHETICAL:"+i,"New identity "+i,amount));
        plans.add(plan("NEW_DISTINCT_IDENTITIES",months,count,identities,additions));
      }
    }
    out.put("status",plans.isEmpty()?"INSUFFICIENT_ALLOCATION_EVIDENCE":"MONTHLY_ILLUSTRATIONS_AVAILABLE");
    out.put("recorded_value",total);out.put("existing_identity_count",identities.size());out.put("plans",plans);
    return out;
  }
  private static BigDecimal monthly(BigDecimal total,int months){
    return total.divide(BigDecimal.valueOf(months),2,RoundingMode.CEILING);
  }
  private static Plan plan(String kind,int months,int newCount,List<Identity> identities,List<Addition> additions){
    BigDecimal monthly=additions.stream().map(Addition::monthlyAmount).reduce(ZERO,BigDecimal::add);
    BigDecimal charge=monthly.multiply(new BigDecimal("0.005")).setScale(2,RoundingMode.HALF_UP);
    Concentration midpoint=project(identities,additions,months/2);
    Concentration end=project(identities,additions,months);
    return new Plan(kind,months,newCount,monthly,monthly.multiply(BigDecimal.valueOf(months)),charge,
      monthly.add(charge),midpoint.largest(),midpoint.topThree(),end.largest(),end.topThree(),end.within(),additions);
  }
  private static Concentration project(List<Identity> identities,List<Addition> additions,int months){
    Map<String,BigDecimal> values=new TreeMap<>();
    for(Identity i:identities)values.put(i.identity(),i.value());
    for(Addition a:additions)values.merge(a.identity(),a.monthlyAmount().multiply(BigDecimal.valueOf(months)),BigDecimal::add);
    return concentration(values.values().stream().toList());
  }
  private static Concentration concentration(List<BigDecimal> values){
    var sorted=values.stream().sorted(Comparator.reverseOrder()).toList();
    BigDecimal total=sorted.stream().reduce(ZERO,BigDecimal::add),largest=sorted.getFirst(),
      top=sorted.stream().limit(3).reduce(ZERO,BigDecimal::add);
    return new Concentration(largest.multiply(HUNDRED).divide(total,4,RoundingMode.HALF_UP),
      top.multiply(HUNDRED).divide(total,4,RoundingMode.HALF_UP),
      largest.compareTo(total.multiply(new BigDecimal("0.25")))<=0&&top.compareTo(total.multiply(new BigDecimal("0.60")))<=0);
  }
}
