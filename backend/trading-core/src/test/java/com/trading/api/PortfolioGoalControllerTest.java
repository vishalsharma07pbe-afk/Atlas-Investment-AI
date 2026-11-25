package com.trading.api;

import java.math.BigDecimal;
import java.time.LocalDate;
import org.junit.jupiter.api.Test;
import org.springframework.web.server.ResponseStatusException;
import static org.junit.jupiter.api.Assertions.*;

class PortfolioGoalControllerTest {
  private static final LocalDate TODAY=LocalDate.of(2026,11,25);
  private BigDecimal n(String v){return new BigDecimal(v);}
  private PortfolioGoalController.Input goal(String balance,String monthly,LocalDate recorded,LocalDate deadline){
    return new PortfolioGoalController.Input("Goal",n("100000"),n(balance),recorded,deadline,n(monthly));
  }
  private void eq(String expected,BigDecimal actual){assertEquals(0,n(expected).compareTo(actual));}
  @Test void calculatesRemainingMonthEndsAndRequiredContribution(){
    var p=PortfolioGoalController.progress(goal("40000","15000",TODAY,LocalDate.of(2027,2,15)),TODAY);
    assertEquals(3,p.remainingMonthEnds());assertEquals("FUNDING_SHORTFALL",p.status());
    eq("40",p.recordedProgressPercent());eq("60000",p.recordedGap());
    eq("85000",p.zeroGrowthProjectedBalance());eq("15000",p.zeroGrowthShortfall());
    eq("20000",p.requiredMonthlyContribution());eq("5000",p.additionalMonthlyContribution());
  }
  @Test void exactMonthEndIsNotCountedWhenAlreadyToday(){
    var today=LocalDate.of(2026,11,30);
    var p=PortfolioGoalController.progress(goal("99999","0",today,LocalDate.of(2027,1,31)),today);
    assertEquals(2,p.remainingMonthEnds());eq("0.50",p.requiredMonthlyContribution());
    var due=PortfolioGoalController.progress(goal("99999","100",today,today),today);
    assertEquals("NO_REMAINING_MONTH_ENDS",due.status());assertNull(due.requiredMonthlyContribution());
    eq("1",due.zeroGrowthShortfall());
  }
  @Test void staleBalanceWithholdsForwardEstimatesAndDoesNotCreditPlannedPayments(){
    var p=PortfolioGoalController.progress(goal("40000","20000",TODAY.minusDays(31),TODAY.plusMonths(3)),TODAY);
    assertEquals("STALE_RECORDED_BALANCE",p.status());eq("40",p.recordedProgressPercent());
    assertNull(p.zeroGrowthProjectedBalance());assertNull(p.requiredMonthlyContribution());
    var current=PortfolioGoalController.progress(goal("40000","20000",TODAY.minusDays(30),TODAY.plusMonths(3)),TODAY);
    assertEquals("FUNDED_UNDER_ZERO_GROWTH",current.status());eq("60000",current.recordedGap());
  }
  @Test void validationRejectsFutureBalanceAndExcessPrecision(){
    assertThrows(ResponseStatusException.class,()->PortfolioGoalController.validate(goal("0","1",TODAY.plusDays(1),TODAY),TODAY));
    assertThrows(ResponseStatusException.class,()->PortfolioGoalController.validate(goal("0","1.001",TODAY,TODAY),TODAY));
    assertDoesNotThrow(()->PortfolioGoalController.validate(goal("0","0",TODAY,TODAY.minusDays(1)),TODAY));
  }
  @Test void linkedValuesAddOnlyCompleteRecentRecordedFunding(){
    var input=goal("40000","15000",TODAY,LocalDate.of(2027,2,15));
    var holding=new PortfolioGoalController.LinkedHolding(1,"TEST","EQUITY","RECENT_RECORDED",n("20000"));
    var funding=PortfolioGoalController.funding(input,java.util.List.of(holding));
    eq("60000",funding.totalRecordedFunding());
    var p=PortfolioGoalController.linkedProgress(input,funding,TODAY);
    eq("60",p.recordedProgressPercent());eq("40000",p.recordedGap());eq("13333.34",p.requiredMonthlyContribution());
    assertEquals("FUNDED_UNDER_ZERO_GROWTH",p.status());
    for(String status:java.util.List.of("MISSING_HOLDING","UNAVAILABLE_RECENT_VALUE")){
      var missing=new PortfolioGoalController.LinkedHolding(2,"OTHER","MUTUAL_FUND",status,null);
      var incomplete=PortfolioGoalController.funding(input,java.util.List.of(holding,missing));
      assertNull(incomplete.totalRecordedFunding());assertNull(incomplete.linkedValue());
      var withheld=PortfolioGoalController.linkedProgress(input,incomplete,TODAY);
      assertEquals("INCOMPLETE_LINKED_VALUATION",withheld.status());assertNull(withheld.recordedProgressPercent());
      assertNull(withheld.recordedGap());assertNull(withheld.requiredMonthlyContribution());
    }
    eq("40000",PortfolioGoalController.funding(input,java.util.List.of()).totalRecordedFunding());
  }

  @Test void goalAttentionDistinguishesShortfallsDeadlinesAndUnavailableEvidence(){
    var today=TODAY;
    var cases=java.util.List.of(
      goal("40000","1000",today,today.plusMonths(6)),
      goal("40000","100000",today,today.plusDays(25)),
      goal("40000","0",today,today.plusDays(1)),
      goal("40000","1000",today.minusDays(31),today.plusMonths(6)),
      goal("100000","0",today,today.plusMonths(6)));
    var expected=java.util.Arrays.asList("SHORTFALL","DEADLINE_NEAR","DEADLINE_GAP","STALE_BALANCE",null);
    for(int i=0;i<cases.size();i++){
      var input=cases.get(i);
      var funding=PortfolioGoalController.funding(input,java.util.List.of());
      var g=new PortfolioGoalController.Goal(java.util.UUID.randomUUID(),input.name(),input.targetAmount(),input.reservedAmount(),
        input.balanceDate(),input.deadline(),input.monthlyContribution(),PortfolioGoalController.linkedProgress(input,funding,today),funding);
      var attention=PortfolioGoalNotifications.attention(g,today);
      assertEquals(expected.get(i),attention==null?null:attention.kind());
    }
  }

}
