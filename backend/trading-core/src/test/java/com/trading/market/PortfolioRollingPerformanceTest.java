package com.trading.market;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.*;
import java.util.stream.IntStream;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static com.trading.market.PortfolioFlowAdjustedPerformance.*;

class PortfolioRollingPerformanceTest {
  private static final LocalDate START=LocalDate.of(2025,1,1);
  private static Observation obs(int d,String value){return new Observation(START.plusDays(d),new BigDecimal(value),true);}
  private static PortfolioRollingPerformance.BenchmarkPoint point(int d,String value,String source,boolean valid){
    return new PortfolioRollingPerformance.BenchmarkPoint(START.plusDays(d),new BigDecimal(value),source,valid);
  }
  @Test void comparesOnlyExactDatesAndSingleEligiblePriceSource(){
    var observations=IntStream.rangeClosed(0,30).mapToObj(d->obs(d,d==30?"1100":"1000")).toList();
    var points=List.of(point(0,"200","SOURCE",true),point(30,"210","SOURCE",true));
    var window=PortfolioRollingPerformance.windows(observations,List.of(),points).getFirst();
    assertEquals("AVAILABLE_ESTIMATE",window.status());
    assertEquals("AVAILABLE_PRICE_REFERENCE",window.benchmarkStatus());
    assertEquals(10,window.returnPercent(),1e-9);
    assertEquals(5,window.benchmarkReturnPercent(),1e-9);
    assertEquals(5,window.relativePercentagePoints(),1e-9);
    for(var bad:List.of(List.of(point(0,"200","SOURCE",true),point(30,"210","OTHER",true)),
        List.of(point(0,"200","SOURCE",true),point(30,"210","SOURCE",false)),
        List.of(point(0,"200","SOURCE",true),point(30,"210","SOURCE",true),point(30,"210","SOURCE",true)))){
      assertNull(PortfolioRollingPerformance.windows(observations,List.of(),bad).getFirst().benchmarkReturnPercent());
    }
    assertEquals("UNAVAILABLE_EXACT_START_DATE",PortfolioRollingPerformance.windows(observations.subList(1,31),List.of(),points).getFirst().status());
    assertEquals("UNAVAILABLE_EXACT_BENCHMARK_ENDPOINTS",PortfolioRollingPerformance.windows(observations,List.of(),List.of(point(1,"200","SOURCE",true),point(30,"210","SOURCE",true))).getFirst().benchmarkStatus());
  }
  @Test void recentWindowSurvivesOlderGapAndWeeklyRiskUsesEqualIntervals(){
    var recent=IntStream.rangeClosed(0,13).mapToObj(i->obs(i*7,i==13?"900":"1000")).toList();
    var risk=PortfolioRollingPerformance.risk(recent,List.of());
    assertEquals("AVAILABLE_ESTIMATE",risk.status());
    assertEquals(13,risk.weeklyObservations());
    assertEquals(20,risk.annualizedDownsideDeviationPercent(),1e-9);
    assertEquals(100.0/13,risk.negativeWeekFrequencyPercent(),1e-9);
    assertEquals("UNAVAILABLE_EXACT_WEEKLY_HISTORY",PortfolioRollingPerformance.risk(recent.subList(1,14),List.of()).status());
    var history=new ArrayList<Observation>();history.add(obs(-100,"1000"));
    history.addAll(IntStream.rangeClosed(0,30).mapToObj(d->obs(d,"1000")).toList());
    assertEquals("AVAILABLE_ESTIMATE",PortfolioRollingPerformance.windows(history,List.of(),List.of()).getFirst().status());
  }
}
