package com.trading.market;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.*;
import java.util.stream.IntStream;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static com.trading.market.PortfolioFlowAdjustedPerformance.*;
import static com.trading.market.PortfolioRollingPerformance.BenchmarkPoint;

class PortfolioBenchmarkRiskTest {
  private static final LocalDate START=LocalDate.of(2025,1,3);
  private static final LocalDate END=START.plusWeeks(13);
  private static List<Observation> observations(boolean lag){
    return IntStream.rangeClosed(0,13).mapToObj(i->new Observation(START.plusWeeks(i),
      BigDecimal.valueOf(lag?1000:1000+10*i+(i%2==0?0:5)),true)).toList();
  }
  private static List<BenchmarkPoint> benchmark(){
    return IntStream.rangeClosed(0,13).mapToObj(i->new BenchmarkPoint(START.plusWeeks(i),
      BigDecimal.valueOf(1000+10*i+(i%2==0?0:5)),"SOURCE",true)).toList();
  }
  @Test void identicalReturnsHaveUnitBetaAndZeroTrackingError(){
    var result=PortfolioBenchmarkRisk.assess(observations(false),List.of(),benchmark(),END);
    assertEquals("AVAILABLE_PRICE_REFERENCE_ESTIMATE",result.status());
    assertEquals(13,result.matchedWeeks());
    assertEquals(1,result.beta(),1e-9);
    assertEquals(0,result.annualizedTrackingErrorPercent(),1e-9);
    assertNull(result.informationRatio());
    assertEquals(0,result.relativePercentagePoints(),1e-9);
    assertEquals("NO_RELATIVE_LAG_FLAG",result.attentionStatus());
  }
  @Test void flatPortfolioAgainstRisingIndexTriggersReviewNotTrade(){
    var result=PortfolioBenchmarkRisk.assess(observations(true),List.of(),benchmark(),END);
    assertEquals("REVIEW_RELATIVE_LAG",result.attentionStatus());
    assertEquals(0,result.portfolioReturnPercent(),1e-9);
    assertEquals(-13.5,result.relativePercentagePoints(),1e-9);
    assertEquals(0,result.beta(),1e-9);
    assertTrue(result.informationRatio()<0);
  }
  @Test void rejectsStaleDuplicateMixedAndMissingBenchmarkAnchors(){
    var obs=observations(false);var points=benchmark();
    assertEquals("UNAVAILABLE_STALE_OR_FUTURE_VALUATION",PortfolioBenchmarkRisk.assess(obs,List.of(),points,END.plusDays(8)).status());
    assertEquals("UNAVAILABLE_EXACT_BENCHMARK_ANCHORS",PortfolioBenchmarkRisk.assess(obs,List.of(),points.subList(1,14),END).status());
    var bad=new ArrayList<>(points);bad.add(points.getFirst());
    assertEquals("UNAVAILABLE_BENCHMARK_QUALITY",PortfolioBenchmarkRisk.assess(obs,List.of(),bad,END).status());
    bad=new ArrayList<>(points);bad.set(1,new BenchmarkPoint(START.plusWeeks(1),BigDecimal.TEN,"OTHER",true));
    assertEquals("INSUFFICIENT_EVIDENCE",PortfolioBenchmarkRisk.assess(obs,List.of(),bad,END).attentionStatus());
  }
}
