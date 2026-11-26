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
  @Test void hiddenSectorRequiresClassifiedCurrentDatedLookThrough(){
    var holdings=List.of(Map.of("recorded_market_value",100,"recorded_valuation_recent",true));
    var flag=Map.of("kind","HIDDEN_SECTOR_CONCENTRATION","label","energy combined sector exposure","value",59,
      "threshold",40,"unit","PERCENT","evidenceThrough","2026-10-31");
    var look=new LinkedHashMap<String,Object>(Map.of("status","DATED_PARTIAL_EQUITY_EXPOSURE_ESTIMATE",
      "portfolio_date","2026-10-31","risk_observations",List.of(flag)));
    var report=Map.<String,Object>of("holdings",holdings,"diversification",Map.of("look_through",look));
    assertEquals(List.of(),PortfolioLevelRisk.assess(report,json,today).get("attention"));
    look.put("sector_status","PARTIAL_CLASSIFIED_EXPOSURE");
    assertEquals(1,((List<?>)PortfolioLevelRisk.assess(report,json,today).get("attention")).size());
    look.put("portfolio_date","2026-09-01");
    assertEquals(List.of(),PortfolioLevelRisk.assess(report,json,today).get("attention"));
  }
  @Test void lookThroughRequiresCurrentValuationsAndDatedMatchingObservations(){
    var holdings=List.of(Map.of("recorded_market_value",100,"recorded_valuation_recent",true));
    var flag=Map.of("kind","HIDDEN_EQUITY_CONCENTRATION","label","Combined exposure","value",30,
      "threshold",25,"unit","PERCENT","evidenceThrough","2026-10-31");
    var look=new LinkedHashMap<String,Object>(Map.of("status","DATED_PARTIAL_EQUITY_EXPOSURE_ESTIMATE",
      "portfolio_date","2026-10-31","risk_observations",List.of(flag)));
    var report=Map.<String,Object>of("holdings",holdings,"diversification",Map.of("look_through",look));
    var result=PortfolioLevelRisk.assess(report,json,today);
    assertEquals("DATED_PARTIAL_EQUITY_EXPOSURE_ESTIMATE",result.get("look_through_status"));
    assertEquals(1,((List<?>)result.get("attention")).size());
    look.put("portfolio_date","2026-09-01");
    result=PortfolioLevelRisk.assess(report,json,today);
    assertEquals("INSUFFICIENT_EVIDENCE",result.get("look_through_status"));
    assertEquals(List.of(),result.get("attention"));
    look.put("portfolio_date","2026-11-01");
    assertEquals(List.of(),PortfolioLevelRisk.assess(report,json,today).get("attention"));
  }

}
