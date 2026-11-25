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
}
