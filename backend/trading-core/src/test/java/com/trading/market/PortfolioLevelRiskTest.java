package com.trading.market;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.LocalDate;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PortfolioLevelRiskTest {
  private final ObjectMapper json=new ObjectMapper();
  private final LocalDate today=LocalDate.of(2026,11,25);
  private Map<String,Object> report(boolean recent,double coverage,LocalDate through,double gap){
    var holdings=List.of(Map.of("recorded_market_value",60,"recorded_valuation_recent",recent),
      Map.of("recorded_market_value",40,"recorded_valuation_recent",true));
    var div=Map.of("unpriced_count",0,"unresolved_identity_count",0,"resolved_identity_count",2,
      "sector_coverage_percent",coverage,"concentration_observations",List.of(
        Map.of("kind","SINGLE_IDENTITY","label","Example","weight_percent",60),
        Map.of("kind","TOP_THREE","label","Top three","weight_percent",100),
        Map.of("kind","DIRECT_EQUITY_SECTOR","label","Energy","weight_percent",60)));
    var benchmark=new PortfolioBenchmarkRisk.Assessment("AVAILABLE_PRICE_REFERENCE_ESTIMATE",13,
      through.minusWeeks(13).toString(),through.toString(),2.0,2.0-gap,gap,null,null,null,
      gap<=-5?"REVIEW_RELATIVE_LAG":"NO_RELATIVE_LAG_FLAG");
    return Map.of("holdings",holdings,"diversification",div,"benchmark_risk_estimate",benchmark);
  }
  @Test void flagsQualifiedBenchmarkAndConcentrationEvidence(){
    var result=PortfolioLevelRisk.assess(report(true,100,today,-6),json,today);
    assertEquals("COMPARABLE_PRICE_REFERENCE",result.get("benchmark_status"));
    assertEquals("RECENT_RECORDED_EXPOSURES",result.get("concentration_status"));
    assertEquals(4,((List<?>)result.get("attention")).size());
  }
  @Test void staleValuationsAndBenchmarkAreWithheld(){
    var result=PortfolioLevelRisk.assess(report(false,100,today.minusDays(8),-6),json,today);
    assertEquals("INSUFFICIENT_EVIDENCE",result.get("benchmark_status"));
    assertEquals("INSUFFICIENT_EVIDENCE",result.get("concentration_status"));
    assertEquals(0,((List<?>)result.get("attention")).size());
  }
  @Test void partialSectorCoverageAndNoRelativeLagDoNotTriggerThoseFlags(){
    var result=PortfolioLevelRisk.assess(report(true,60,today,-2),json,today);
    assertEquals("INSUFFICIENT_EVIDENCE",result.get("sector_status"));
    assertEquals(2,((List<?>)result.get("attention")).size());
  }
  @Test void missingEvidenceIsNotAnAssessment(){
    var result=PortfolioLevelRisk.assess(Map.of(),json,today);
    assertEquals("INSUFFICIENT_EVIDENCE",result.get("benchmark_status"));
    assertEquals("INSUFFICIENT_EVIDENCE",result.get("concentration_status"));
    assertEquals(List.of(),result.get("attention"));
  }
}
