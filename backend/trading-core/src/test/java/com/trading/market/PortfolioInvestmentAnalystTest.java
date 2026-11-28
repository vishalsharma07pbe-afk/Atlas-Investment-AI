package com.trading.market;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import java.time.LocalDate;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class PortfolioInvestmentAnalystTest {
  final ObjectMapper json=new ObjectMapper();
  final LocalDate today=LocalDate.of(2026,11,28);
  Map<String,Object> holding(double weight,double score){
    var h=new LinkedHashMap<String,Object>();
    h.put("asset_type","EQUITY");h.put("status","MONITOR");h.put("weight_percent",weight);
    h.put("recorded_valuation_recent",true);h.put("evidence_date","2026-11-27");
    h.put("recorded_return_percent",-50);
    h.put("reassessment",Map.of("status","PRELIMINARY_SCORE_ONLY","score",score,"missing_factors",List.of(),
       "review_state","MONITOR_RESEARCH_ONLY"));
    return h;
  }
  String action(Map<String,Object> h,boolean coverage){
    return (String)PortfolioInvestmentAnalyst.holding(json.valueToTree(h),today,coverage).get("action");
  }
  @Test void distinguishesBusinessRiskConcentrationAndPriceLoss(){
    var h=holding(10,80);
    assertEquals("COMPARE_FOR_ACCUMULATION",action(h,true));
    h.put("weight_percent",30);
    assertEquals("REBALANCE_REVIEW",action(h,true));
    h.put("thesis_changes",List.of(Map.of("current_direction","DECLINING")));
    assertEquals("REVIEW_REDUCTION",action(h,true));
    assertEquals("REVIEW_REDUCTION",action(h,false));
  }
  @Test void missingEvidenceAndWeakScoreDoNotGenerateBuys(){
    var h=holding(10,30);
    assertEquals("REASSESS_THESIS",action(h,true));
    h.put("evidence_date","2026-10-01");
    assertEquals("HOLD_PENDING_EVIDENCE",action(h,true));
    h.put("evidence_date","2026-11-27");
    h.put("status","REVIEW_REQUIRED");
    assertEquals("PAUSE_ADDITIONS",action(h,true));
  }
  @Test void noCrossAssetScoringOrFalseCoverage(){
    var h=holding(10,90);h.put("asset_type","MUTUAL_FUND");
    assertEquals("HOLD_MONITOR",action(h,true));
    var out=PortfolioInvestmentAnalyst.attach(Map.of("holdings",List.of(h)),json,today);
    assertEquals("HOLD_PENDING_EVIDENCE",json.valueToTree(out).path("holdings").get(0).path("investment_analysis").path("action").asText());
    assertFalse(json.valueToTree(out).path("investment_analysis").path("recent_weight_coverage").asBoolean());
    assertFalse(h.containsKey("investment_analysis"));
  }
  @Test void scenarioRequiresCompleteWeightsAndNeverInfersForecast(){
    var equity=holding(60,80);var fund=holding(40,80);fund.put("asset_type","MUTUAL_FUND");
    var result=json.valueToTree(PortfolioInvestmentAnalyst.attach(Map.of("holdings",List.of(equity,fund)),json,today));
    var stress=result.path("investment_analysis").path("stress_test");
    assertEquals("ILLUSTRATIVE_SHOCKS",stress.path("status").asText());
    assertEquals(-26.0,stress.path("scenarios").get(0).path("portfolio_change_percent").asDouble(),.00001);
    assertEquals(.52,stress.path("position_hhi").asDouble(),.00001);
    fund.put("recorded_valuation_recent",false);
    result=json.valueToTree(PortfolioInvestmentAnalyst.attach(Map.of("holdings",List.of(equity,fund)),json,today));
    assertEquals("AWAITING_COMPLETE_RECORDED_WEIGHTS",result.path("investment_analysis").path("stress_test").path("status").asText());
  }
}
