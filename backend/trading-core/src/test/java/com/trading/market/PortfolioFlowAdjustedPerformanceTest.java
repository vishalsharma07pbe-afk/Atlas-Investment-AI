package com.trading.market;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PortfolioFlowAdjustedPerformanceTest {
  private static final LocalDate DAY=LocalDate.of(2026,11,1);
  private static PortfolioFlowAdjustedPerformance.Observation obs(int day,String value){
    return new PortfolioFlowAdjustedPerformance.Observation(DAY.plusDays(day),new BigDecimal(value),true);
  }
  private static PortfolioFlowAdjustedPerformance.Flow flow(int day,String value){
    return new PortfolioFlowAdjustedPerformance.Flow(DAY.plusDays(day),new BigDecimal(value));
  }

  @Test void depositsAndWithdrawalsAloneDoNotCreateInvestmentReturns(){
    var result=PortfolioFlowAdjustedPerformance.calculate(
      List.of(obs(0,"1000"),obs(1,"1500"),obs(2,"1200")),
      List.of(flow(0,"1000"),flow(1,"500"),flow(2,"-300"),flow(3,"999")));
    assertEquals("AVAILABLE_ESTIMATE",result.status());
    assertEquals(0.0,result.returnPercent(),1e-9);
    assertEquals(0.0,result.drawdownPercent(),1e-9);
    assertEquals(2,result.flowCount());
  }

  @Test void weightsMidIntervalContributionsAndCompoundsInvestmentLoss(){
    var result=PortfolioFlowAdjustedPerformance.calculate(
      List.of(obs(0,"1000"),obs(2,"1625"),obs(3,"1462.5")),
      List.of(flow(1,"500")));
    assertEquals("AVAILABLE_ESTIMATE",result.status());
    assertEquals(-1.0,result.returnPercent(),1e-9);
    assertEquals(-10.0,result.drawdownPercent(),1e-9);
    assertEquals(2L,result.maximumIntervalDays().longValue());
  }

  @Test void rejectsSparseIncompleteAndInvalidCapitalHistories(){
    assertEquals("UNAVAILABLE_VALUATION_GAPS",PortfolioFlowAdjustedPerformance.calculate(
      List.of(obs(0,"1000"),obs(8,"1100")),List.of()).status());
    var incomplete=new PortfolioFlowAdjustedPerformance.Observation(DAY.plusDays(1),BigDecimal.ONE,false);
    assertEquals("UNAVAILABLE_INCOMPLETE_VALUATIONS",PortfolioFlowAdjustedPerformance.calculate(
      List.of(obs(0,"1000"),incomplete),List.of()).status());
    assertEquals("UNAVAILABLE_NONPOSITIVE_CAPITAL_BASE",PortfolioFlowAdjustedPerformance.calculate(
      List.of(obs(0,"1000"),obs(2,"100")),List.of(flow(1,"-2000"))).status());
    assertEquals("UNAVAILABLE_INCONSISTENT_CASH_FLOWS",PortfolioFlowAdjustedPerformance.calculate(
      List.of(obs(0,"1000"),obs(1,"500")),List.of(flow(1,"900"))).status());
    assertEquals("UNAVAILABLE_INVALID_VALUATION_ORDER",PortfolioFlowAdjustedPerformance.calculate(
      List.of(obs(0,"1000"),obs(0,"1100")),List.of()).status());
  }

  @Test void preservesObservedReturnAndDrawdownWithoutFlows(){
    var result=PortfolioFlowAdjustedPerformance.calculate(
      List.of(obs(0,"1000"),obs(1,"900"),obs(2,"1100")),List.of());
    assertEquals(10.0,result.returnPercent(),1e-9);
    assertEquals(-10.0,result.drawdownPercent(),1e-9);
  }
}
