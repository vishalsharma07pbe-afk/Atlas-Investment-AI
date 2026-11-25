package com.trading.market;

import java.time.LocalDate;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PortfolioAllocationValidationTest {
  private List<PortfolioEquityCorrelation.Interval> dates(int n){
    List<PortfolioEquityCorrelation.Interval> result=new ArrayList<>();
    LocalDate start=LocalDate.of(2026,9,1);
    for(int i=0;i<n;i++)result.add(new PortfolioEquityCorrelation.Interval(start.plusDays(i),start.plusDays(i+1)));
    return result;
  }
  private double[][] observations(int n,boolean reversal){
    double[][] result=new double[n][2];
    for(int i=0;i<n;i++){
      double sign=i%2==0?1:-1;
      result[i][0]=sign*0.02;
      result[i][1]=i>=40&&reversal?sign*0.08:-sign*0.02;
    }
    return result;
  }
  @Test void frozenSelectionCanFailOnLaterObservations(){
    var report=PortfolioAllocationValidation.assess(new double[]{0.8,0.2},observations(60,true),dates(60));
    assertEquals("CONDITIONAL_HOLDOUT_AVAILABLE",report.get("status"));
    assertEquals(40,report.get("selection_count"));
    assertEquals(20,report.get("holdout_count"));
    assertEquals("EQUAL_WEIGHTS",report.get("selected_kind"));
    assertEquals("HIGHER_OBSERVED_HOLDOUT_VARIABILITY",report.get("comparison"));
    assertTrue((Double)report.get("holdout_volatility_difference_pp")>0);
    assertEquals(report.get("selection_through"),report.get("holdout_from"));
  }
  @Test void changingHoldoutCannotChangeSelectedCandidate(){
    var stable=PortfolioAllocationValidation.assess(new double[]{0.8,0.2},observations(60,false),dates(60));
    var changed=PortfolioAllocationValidation.assess(new double[]{0.8,0.2},observations(60,true),dates(60));
    assertEquals(stable.get("selected_kind"),changed.get("selected_kind"));
    assertEquals("LOWER_OBSERVED_HOLDOUT_VARIABILITY",stable.get("comparison"));
  }
  @Test void equalCandidatesKeepCurrentWeights(){
    var report=PortfolioAllocationValidation.assess(new double[]{0.5,0.5},observations(60,false),dates(60));
    assertEquals("CURRENT_WEIGHTS",report.get("selected_kind"));
    assertEquals("BASELINE_SELECTED",report.get("comparison"));
  }
  @Test void shortHistoryWithholdsValidation(){
    var report=PortfolioAllocationValidation.assess(new double[]{0.8,0.2},observations(44,false),dates(44));
    assertEquals("INSUFFICIENT_HOLDOUT_HISTORY",report.get("status"));
    assertEquals(List.of(),report.get("metrics"));
    assertFalse(report.containsKey("selected_kind"));
  }
}
