package com.trading.market;

import java.math.BigDecimal;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PortfolioMonthlyContributionsTest {
  private BigDecimal n(String s){return new BigDecimal(s);}
  private void eq(String expected,BigDecimal actual){assertEquals(0,n(expected).compareTo(actual));}
  private Map<String,Object> assess(boolean complete,String... values){
    List<PortfolioMonthlyContributions.Identity> identities=new ArrayList<>();
    for(int i=0;i<values.length;i++)identities.add(new PortfolioMonthlyContributions.Identity("AMFI:"+ (123456+i),"Fund "+i,n(values[i])));
    var amounts=identities.stream().map(PortfolioMonthlyContributions.Identity::value).toList();
    BigDecimal total=amounts.stream().reduce(BigDecimal.ZERO,BigDecimal::add);
    return PortfolioMonthlyContributions.assess(identities,total,PortfolioAllocationResearch.assess(amounts,total,complete),complete);
  }
  private List<PortfolioMonthlyContributions.Plan> plans(Map<String,Object> report){
    return ((List<?>)report.get("plans")).stream().map(PortfolioMonthlyContributions.Plan.class::cast).toList();
  }
  @Test void singleIdentityProducesFourHorizonsForEachDistinctNewIdentityScenario(){
    var result=assess(true,"1000");
    assertEquals("MONTHLY_ILLUSTRATIONS_AVAILABLE",result.get("status"));
    var plans=plans(result);assertEquals(8,plans.size());
    var p=plans.stream().filter(x->x.months()==12&&x.hypotheticalNewIdentities()==5).findFirst().orElseThrow();
    eq("250",p.monthlyContribution());eq("3000",p.totalContribution());
    eq("1.25",p.monthlyChargeAt50Bps());eq("251.25",p.monthlyCashAt50Bps());
    eq("40",p.midpointLargestPercent());eq("64",p.midpointTopThreePercent());
    eq("25",p.finalLargestPercent());eq("55",p.finalTopThreePercent());
    assertTrue(p.meetsIllustrativeLimits());
    for(var plan:plans){
      assertTrue(plan.meetsIllustrativeLimits());
      assertEquals(plan.hypotheticalNewIdentities(),plan.allocations().size());
      assertEquals(0,plan.monthlyContribution().multiply(BigDecimal.valueOf(plan.months())).compareTo(plan.totalContribution()));
    }
  }
  @Test void existingIdentityTopUpsAvoidNewHoldingsAndExcludeLargest(){
    var plans=plans(assess(true,"1000","400","400","400","400"));
    var p=plans.stream().filter(x->x.kind().equals("EXISTING_IDENTITY_EQUALIZATION")&&x.months()==12).findFirst().orElseThrow();
    eq("200",p.monthlyContribution());eq("2400",p.totalContribution());
    assertEquals(4,p.allocations().size());assertEquals(0,p.hypotheticalNewIdentities());
    assertTrue(p.allocations().stream().noneMatch(a->a.identity().equals("AMFI:123456")));
    eq("20",p.finalLargestPercent());eq("60",p.finalTopThreePercent());assertTrue(p.meetsIllustrativeLimits());
  }
  @Test void exactThresholdChecksDoNotHideRoundingOvershoot(){
    var p=plans(assess(true,"1000","400.01","400.02","400.03","400.04")).stream()
      .filter(x->x.kind().equals("EXISTING_IDENTITY_EQUALIZATION")&&x.months()==12).findFirst().orElseThrow();
    assertFalse(p.meetsIllustrativeLimits());
  }
  @Test void insufficientEvidenceAndAlreadyWithinLimitsDoNotCreatePlans(){
    assertEquals("INSUFFICIENT_RECENT_EXACT_VALUATIONS",assess(false,"1000").get("status"));
    assertEquals("WITHIN_ILLUSTRATIVE_LIMITS",assess(true,"20","20","20","20","20").get("status"));
    assertTrue(plans(assess(false,"1000")).isEmpty());
  }
}
