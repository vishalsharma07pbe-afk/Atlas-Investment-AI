package com.trading.market;

import java.math.BigDecimal;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PortfolioAllocationResearchTest {
  private Map<String,Object> assess(boolean complete,String... input){
    var amounts=Arrays.stream(input).map(BigDecimal::new).toList();
    return PortfolioAllocationResearch.assess(amounts,amounts.stream().reduce(BigDecimal.ZERO,BigDecimal::add),complete);
  }
  private PortfolioAllocationResearch.Scenario scenario(Map<String,Object> report,int i){
    return (PortfolioAllocationResearch.Scenario)((List<?>)report.get("scenarios")).get(i);
  }
  private void equal(String expected,BigDecimal actual){
    assertEquals(0,new BigDecimal(expected).compareTo(actual));
  }
  @Test void singleIdentityRequiresThreeTimesCapitalOrThreeQuartersRedistribution(){
    var result=assess(true,"1000");
    assertEquals("HYPOTHETICAL_SCENARIOS_AVAILABLE",result.get("status"));
    var costs=(Map<?,?>)result.get("cost_sensitivity");
    var rows=((List<?>)costs.get("scenarios")).stream().map(PortfolioRebalancingCosts.Row.class::cast).toList();
    assertEquals(4,rows.size());
    equal("3000",rows.get(0).grossNotional());
    equal("3015",rows.get(0).estimates().get(1).additionalCashIncludingCost());
    equal("1500",rows.get(1).grossNotional());
    equal("7.5",rows.get(1).estimates().get(1).additionalCashIncludingCost());
    for(int i=0;i<2;i++){
      var s=scenario(result,i);
      equal("3000",s.additionalCapital());equal("25",s.projectedLargestPercent());
      equal("750",s.hypotheticalRedistributedCapital());equal("75",s.redistributedPercent());
      assertTrue(s.projectedTopThreePercent().compareTo(new BigDecimal("60"))<=0);
    }
  }
  @Test void topThreeConstraintIncludesNewIdentitiesAndRounding(){
    var result=assess(true,"100.01","100.01","100.01");
    var s=scenario(result,0);
    equal("200.05",s.additionalCapital());
    for(int i=0;i<2;i++){
      var plan=scenario(result,i);
      assertTrue(plan.projectedLargestPercent().compareTo(new BigDecimal("25"))<=0);
      assertTrue(plan.projectedTopThreePercent().compareTo(new BigDecimal("60"))<=0);
      assertEquals(0,plan.additionalCapital().compareTo(plan.equalNewInvestmentAmount().multiply(BigDecimal.valueOf(plan.hypotheticalNewIdentities()))));
    }
  }
  @Test void exactThresholdIsNotAnExcess(){
    var result=assess(true,"20","20","20","20","20");
    assertEquals("WITHIN_ILLUSTRATIVE_CONCENTRATION_LIMITS",result.get("status"));
    assertEquals(List.of(),result.get("scenarios"));
  }
  @Test void missingOrInconsistentEvidenceWithholdsScenarios(){
    assertEquals("INSUFFICIENT_RECENT_EXACT_VALUATIONS",assess(false,"1000").get("status"));
    assertEquals("INSUFFICIENT_RECENT_EXACT_VALUATIONS",assess(true).get("status"));
    assertEquals("INSUFFICIENT_RECENT_EXACT_VALUATIONS",PortfolioAllocationResearch.assess(List.of(new BigDecimal("100")),new BigDecimal("200"),true).get("status"));
  }
}
