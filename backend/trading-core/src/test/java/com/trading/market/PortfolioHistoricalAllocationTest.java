package com.trading.market;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PortfolioHistoricalAllocationTest {
  private static final String A="INE002A01018",B="INE009A01021";
  private static final LocalDate TODAY=LocalDate.of(2026,11,25);
  private Map<PortfolioEquityCorrelation.Interval,Double> returns(double sign){
    var rows=new HashMap<PortfolioEquityCorrelation.Interval,Double>();
    for(int i=0;i<40;i++){
      var start=TODAY.minusDays(41-i);
      rows.put(new PortfolioEquityCorrelation.Interval(start,start.plusDays(1)),sign*(i%2==0?0.02:-0.02));
    }
    return rows;
  }
  private Map<String,Object> assess(Map<String,Map<PortfolioEquityCorrelation.Interval,Double>> series,boolean complete){
    return PortfolioHistoricalAllocation.assess(Map.of(A,new BigDecimal("800"),B,new BigDecimal("200")),
      Map.of(A,"A",B,"B"),series,TODAY,complete);
  }
  @Test void sameSampleAlternativesExposeObservedVolatilityAndTurnover(){
    var result=assess(Map.of(A,returns(1),B,returns(-1)),true);
    assertEquals("HISTORICAL_COMPARISON_AVAILABLE",result.get("status"));
    assertEquals(40,result.get("observations"));
    assertEquals("EQUAL_WEIGHTS",result.get("lowest_observed_variability"));
    assertEquals("INSUFFICIENT_HOLDOUT_HISTORY",((Map<?,?>)result.get("chronological_validation")).get("status"));
    var plans=((List<?>)result.get("alternatives")).stream().map(PortfolioHistoricalAllocation.Alternative.class::cast).toList();
    assertEquals(3,plans.size());
    assertEquals(1.2*Math.sqrt(40.0/39),plans.get(0).sampleVolatilityPercent(),1e-8);
    assertEquals(0,plans.get(2).sampleVolatilityPercent(),1e-8);
    assertEquals(30,plans.get(2).oneWayTurnoverPercent(),1e-8);
    assertEquals(65,plans.get(1).largestWeightPercent(),1e-8);
    assertEquals(15,plans.get(1).oneWayTurnoverPercent(),1e-8);
    var costs=(Map<?,?>)result.get("cost_sensitivity");
    var rows=((List<?>)costs.get("scenarios")).stream().map(PortfolioRebalancingCosts.Row.class::cast).toList();
    assertEquals(3,rows.size());
    assertEquals(0,new BigDecimal("600").compareTo(rows.get(2).grossNotional()));
    assertEquals(0,new BigDecimal("3").compareTo(rows.get(2).estimates().get(1).hypotheticalCost()));
  }
  @Test void incompleteCoverageAndMissingHistoryWithholdAlternatives(){
    assertEquals("INSUFFICIENT_RECENT_EXACT_DIRECT_EQUITY_COVERAGE",assess(Map.of(A,returns(1),B,returns(1)),false).get("status"));
    assertEquals("INSUFFICIENT_ADJUSTED_HISTORY",assess(Map.of(A,returns(1)),true).get("status"));
  }
  @Test void insufficientCommonIntervalsCannotUsePairwiseOrUnmatchedData(){
    var b=returns(-1);
    b.keySet().removeIf(d->d.end().isBefore(TODAY.minusDays(20)));
    assertEquals("INSUFFICIENT_COMMON_RETURN_INTERVALS",assess(Map.of(A,returns(1),B,b),true).get("status"));
  }
  @Test void equalWeightingNeedNotImproveHistoricalVariability(){
    var result=assess(Map.of(A,returns(0.1),B,returns(1)),true);
    assertEquals("CURRENT_WEIGHTS",result.get("lowest_observed_variability"));
  }
  @Test void bothAllocationModesExposeConditionalValidationOnCommonHistory(){
    var first=new HashMap<PortfolioEquityCorrelation.Interval,Double>();
    var second=new HashMap<PortfolioEquityCorrelation.Interval,Double>();
    for(int k=0;k<60;k++){
      var start=TODAY.minusDays(61-k);
      var interval=new PortfolioEquityCorrelation.Interval(start,start.plusDays(1));
      double sign=k%2==0?1:-1;
      first.put(interval,sign*0.02);
      second.put(interval,k<40?-sign*0.02:sign*0.08);
    }
    var direct=assess(Map.of(A,first,B,second),true);
    var mixed=PortfolioHistoricalAllocation.assessMixed(
      Map.of(A,new BigDecimal("800"),"AMFI:123456",new BigDecimal("200")),Map.of(),
      Map.of(A,first,"AMFI:123456",second),TODAY,true);
    for(var result:List.of(direct,mixed)){
      var validation=(Map<?,?>)result.get("chronological_validation");
      assertEquals("CONDITIONAL_HOLDOUT_AVAILABLE",validation.get("status"));
      assertEquals("EQUAL_WEIGHTS",validation.get("selected_kind"));
      assertEquals("HIGHER_OBSERVED_HOLDOUT_VARIABILITY",validation.get("comparison"));
      assertEquals(40,validation.get("selection_count"));
      assertEquals(20,validation.get("holdout_count"));
    }
  }

}
