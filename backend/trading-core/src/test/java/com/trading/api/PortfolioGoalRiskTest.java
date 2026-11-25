package com.trading.api;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static com.trading.api.PortfolioGoalController.*;

class PortfolioGoalRiskTest {
  private static final LocalDate TODAY=LocalDate.of(2026,11,25);
  private static BigDecimal n(String s){return new BigDecimal(s);}
  private static void eq(String expected,BigDecimal actual){assertNotNull(actual);assertEquals(0,n(expected).compareTo(actual));}
  private Goal goal(String cash,String monthly,LocalDate balance,LocalDate deadline,List<LinkedHolding> holdings){
    var input=new Input("Goal",n("100000"),n(cash),balance,deadline,n(monthly));
    var funding=funding(input,holdings);
    return new Goal(UUID.randomUUID(),input.name(),input.targetAmount(),input.reservedAmount(),
      input.balanceDate(),input.deadline(),input.monthlyContribution(),linkedProgress(input,funding,TODAY),funding);
  }
  private LinkedHolding equity(){return new LinkedHolding(1,"EQ","EQUITY","RECENT_RECORDED",n("40000"));}
  private LinkedHolding fund(){return new LinkedHolding(2,"123456","MUTUAL_FUND","RECENT_RECORDED",n("20000"));}
  @Test void separateAndCombinedShocksOnlyAffectAssignedInvestments(){
    var g=goal("20000","10000",TODAY,LocalDate.of(2027,2,15),List.of(equity(),fund()));
    var r=PortfolioGoalRisk.assess(g,TODAY);
    assertEquals("ILLUSTRATIVE_STRESS_AVAILABLE",r.status());
    assertEquals("NEAR_DEADLINE_FUNDING_REVIEW",r.reviewPriority());
    eq("80000",r.grossWithdrawalGap());eq("50000",r.projectedWithdrawalGap());
    eq("20000",r.grossFundingNotCoveredByAssignedHoldings());eq("0",r.recordedFundingSurplus());
    assertEquals(3,r.scenarios().size());
    eq("8000",r.scenarios().get(0).hypotheticalLoss());eq("2000",r.scenarios().get(1).hypotheticalLoss());
    var combined=r.scenarios().get(2);
    eq("10000",combined.hypotheticalLoss());eq("70000",combined.stressedRecordedFunding());
    eq("100000",combined.projectedFunding());eq("0",combined.projectedShortfall());
    eq("10000",combined.requiredMonthlyContribution());eq("0",combined.additionalMonthlyContribution());
  }
  @Test void deadlineWithNoRemainingContributionDatesDoesNotInventMonthlyFunding(){
    var r=PortfolioGoalRisk.assess(goal("40000","99999",TODAY,TODAY,List.of(equity())),TODAY);
    var s=r.scenarios().getFirst();
    eq("72000",s.projectedFunding());eq("28000",s.projectedShortfall());
    assertNull(s.requiredMonthlyContribution());assertNull(s.additionalMonthlyContribution());
    assertEquals(0,r.daysToDeadline());
  }
  @Test void staleOrMissingValuesWithholdAllScenarioTotals(){
    var stale=goal("20000","10000",TODAY.minusDays(31),TODAY.plusMonths(6),List.of(equity()));
    var missing=goal("20000","10000",TODAY,TODAY.plusMonths(6),List.of(equity(),
      new LinkedHolding(2,"123456","MUTUAL_FUND","MISSING_HOLDING",null)));
    for(var g:List.of(stale,missing)){
      var r=PortfolioGoalRisk.assess(g,TODAY);
      assertEquals("INSUFFICIENT_FUNDING_EVIDENCE",r.status());
      assertTrue(r.scenarios().isEmpty());assertNull(r.grossWithdrawalGap());assertNull(r.equityValue());
    }
  }
  @Test void noLinkedExposureDoesNotInventStressOrLiquidationValue(){
    var r=PortfolioGoalRisk.assess(goal("120000","0",TODAY,TODAY.plusMonths(6),List.of()),TODAY);
    assertEquals("NO_POSITIVE_LINKED_EXPOSURE",r.status());assertEquals("MONITOR",r.reviewPriority());
    eq("20000",r.recordedFundingSurplus());eq("0",r.grossWithdrawalGap());
    assertTrue(r.scenarios().isEmpty());
  }
  @Test void marketDownsideCanCreateGapEvenWhenBaselineMeetsTarget(){
    var g=goal("20000","3000",TODAY,LocalDate.of(2027,6,15),List.of(equity(),fund()));
    eq("0",g.progress().zeroGrowthShortfall());
    var r=PortfolioGoalRisk.assess(g,TODAY);
    assertEquals("DOWNSIDE_FUNDING_REVIEW",r.reviewPriority());
    eq("9000",r.scenarios().getLast().projectedShortfall());
    eq("4285.72",r.scenarios().getLast().requiredMonthlyContribution());
  }
}
