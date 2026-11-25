package com.trading.market;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PortfolioThesisSummaryTest {
 private final ObjectMapper json=new ObjectMapper();
 private static Map<String,Object> ratio(String name,double company,double sector,String unit){
  return Map.of("name",name,"company_value",company,"sector_value",sector,"unit",unit,"sector_unit",unit);
 }
 private static Map<String,Object> equity(List<Map<String,Object>> ratios){
  return Map.of("asset_type","EQUITY","findings",List.of("Recorded concentration risk"),
    "thesis_evidence",Map.of("company_evidence",Map.of("sections",Map.of("ratios",Map.of("data",ratios))),
    "news_evidence",Map.of("status","REVIEW_AVAILABLE","articles",List.of(Map.of("topics",List.of("REGULATORY","UNKNOWN"))))));
 }
 @Test void reportsRecordedRisksAndComparableRatiosWithProvenance(){
  var result=PortfolioThesisSummary.summarize(equity(List.of(ratio("P/E",25,15,"RATIO"),ratio("ROE",20,15,"PERCENT"))),json);
  assertEquals("REVIEW_EVIDENCE",result.get("status"));
  assertTrue(result.get("risks").toString().contains("Recorded concentration risk"));
  assertTrue(result.get("review_prompts").toString().contains("P/E 25.00 vs sector 15.00"));
  assertTrue(result.get("review_prompts").toString().contains("REGULATORY"));
  assertFalse(result.get("review_prompts").toString().contains("UNKNOWN"));
  assertTrue(result.get("observations").toString().contains("ROE 20.00%"));
  assertTrue(result.get("gaps").toString().contains("Official filings"));
 }
 @Test void invalidUnitsNegativeValuationAndDuplicateAliasesCannotProduceComparison(){
  var result=PortfolioThesisSummary.summarize(equity(List.of(ratio("PE",25,15,"RATIO"),
    ratio("P/E",26,15,"RATIO"),ratio("ROE",20,15,"RATIO"),ratio("PB",-2,4,"RATIO"))),json);
  assertEquals(1,((List<?>)result.get("review_prompts")).size());
  assertEquals(0,((List<?>)result.get("observations")).size());
  assertTrue(result.get("gaps").toString().contains("No unambiguous"));
 }
 @Test void exactFundHistoryIsAnObservationNotAForwardForecast(){
  var result=PortfolioThesisSummary.summarize(Map.of("asset_type","MUTUAL_FUND","fund_history_evidence",
    Map.of("cagr_3y_percent",12.5,"drawdown_3y_percent",-25,"weekly_volatility_percent",18)),json);
  assertEquals("REVIEW_EVIDENCE",result.get("status"));
  assertTrue(result.get("observations").toString().contains("12.50%"));
  assertTrue(result.get("review_prompts").toString().contains("-25.00%"));
  assertTrue(result.get("gaps").toString().contains("Riskometer"));
 }
 @Test void annualDeclineIsReviewPromptButStalePeriodsAreNot(){
  var recent=Map.<String,Object>of("metric","NET_PROFIT","previous_year",2024,"latest_year",2025,"previous_value",100,"latest_value",75,"unit","crore","change_percent",-25,"latest_period_may_be_stale",false);
  var stale=Map.<String,Object>of("metric","REVENUE","previous_year",2021,"latest_year",2022,"previous_value",100,"latest_value",50,"unit","crore","latest_period_may_be_stale",true);
  var holding=Map.<String,Object>of("asset_type","EQUITY","thesis_evidence",Map.of("company_evidence",Map.of("financial_trends",Map.of("status","PARTIAL","items",List.of(recent,stale)))));
  var result=PortfolioThesisSummary.summarize(holding,json);
  assertEquals("REVIEW_EVIDENCE",result.get("status"));
  assertTrue(result.get("review_prompts").toString().contains("Net profit FY2024"));
  assertFalse(result.get("review_prompts").toString().contains("FY2021"));
  assertTrue(result.get("gaps").toString().contains("Annual financial statement coverage is partial"));
 }
 @Test void derivedMarginDeclineAppearsInHoldingReview(){
  var metric=Map.<String,Object>of("metric","NET_MARGIN","previous_value",20,"latest_value",15,"unit","PERCENT");
  var holding=Map.<String,Object>of("asset_type","EQUITY","thesis_evidence",Map.of("company_evidence",Map.of("fundamental_quality",Map.of("derived_metrics",List.of(metric)))));
  var result=PortfolioThesisSummary.summarize(holding,json);
  assertEquals("REVIEW_EVIDENCE",result.get("status"));
  assertTrue(result.get("review_prompts").toString().contains("Net margin changed from 20.00% to 15.00%"));
 }
 @Test void missingEvidenceNeverProducesPositiveVerdict(){
  var result=PortfolioThesisSummary.summarize(Map.of("asset_type","EQUITY"),json);
  assertEquals("INSUFFICIENT_FOR_VERDICT",result.get("status"));
  assertTrue(((List<?>)result.get("observations")).isEmpty());
  assertFalse(((List<?>)result.get("gaps")).isEmpty());
 }
}
