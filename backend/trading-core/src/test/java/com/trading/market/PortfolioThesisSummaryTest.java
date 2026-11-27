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
 @Test void heldFundDeteriorationUsesReportedFundWeightAndCoverage(){
  var underlying=Map.of("status","REPORTED_HISTORICAL_DRIVERS_ONLY","annual_statement_weight_percent",60,
    "deterioration_review_weight_percent",25);
  var evidence=Map.of("status","SECONDARY_REPORTED_EVIDENCE","disclosure",Map.of("ter_percent",0.7,"ter_date","2026-11-24","riskometer","VERY_HIGH"),
    "portfolio",Map.of("status","SECONDARY_COMPOSITION_ONLY","portfolio_date","2026-10-31","underlying_research",underlying));
  var report=PortfolioThesisSummary.summarize(Map.of("asset_type","MUTUAL_FUND","fund_thesis_evidence",evidence),json);
  assertEquals("REVIEW_EVIDENCE",report.get("status"));
  assertTrue(report.get("review_prompts").toString().contains("25.00% of reported fund weight"));
  assertTrue(report.get("review_prompts").toString().contains("60.00% has annual statement evidence"));
  assertTrue(report.get("observations").toString().contains("0.70%"));
 }
 @Test void ownershipDeclineIsReviewEvidenceNotProofOfTrades(){
  var ownership=Map.of("status","COMPARABLE_QUARTERS","previous_period","2026-06-30","latest_period","2026-09-30",
    "review_prompts",List.of(Map.of("category","promoters","change_pp",-2)));
  var holding=Map.<String,Object>of("asset_type","EQUITY","thesis_evidence",Map.of("company_evidence",Map.of("ownership_research",ownership)));
  var result=PortfolioThesisSummary.summarize(holding,json);
  assertEquals("REVIEW_EVIDENCE",result.get("status"));
  assertTrue(result.get("review_prompts").toString().contains("ownership fell 2.00 percentage points"));
  assertTrue(result.get("review_prompts").toString().contains("not proof of sales"));
  assertTrue(result.get("gaps").toString().contains("Promoter pledges"));
 }
 @Test void missingEvidenceNeverProducesPositiveVerdict(){
  var result=PortfolioThesisSummary.summarize(Map.of("asset_type","EQUITY"),json);
  assertEquals("INSUFFICIENT_FOR_VERDICT",result.get("status"));
  assertTrue(((List<?>)result.get("observations")).isEmpty());
  assertFalse(((List<?>)result.get("gaps")).isEmpty());
 }
 @Test void quarterlyEvidenceRequiresExactIdentityAndRecentPeriodAndFlagsDeterioration(){
  var period=java.time.LocalDate.now(java.time.ZoneId.of("Asia/Kolkata")).withDayOfMonth(1).minusDays(1).toString();
  var metric=Map.<String,Object>of("metric","net_profit","latest_value",90,
    "year_over_year_growth_percent",-10,"previous_quarter_growth_percent",5,"growth_acceleration_pp",-15);
  var quarter=Map.of("status","PARTIAL_LATEST_QUARTER","latest_period",period,"items",List.of(metric));
  var company=Map.of("isin","INE002A01018","quarterly_financials",quarter);
  var holding=Map.<String,Object>of("asset_type","EQUITY","isin","INE002A01018","thesis_evidence",Map.of("company_evidence",company));
  var report=PortfolioThesisSummary.summarize(holding,json);
  assertTrue(report.get("review_prompts").toString().contains("YoY -10.00%"));
  assertTrue(report.get("review_prompts").toString().contains("not an exit signal"));
  assertTrue(report.get("gaps").toString().contains("quarterly"));
  var mismatched=new LinkedHashMap<>(holding);mismatched.put("isin","INE009A01021");
  assertFalse(PortfolioThesisSummary.summarize(mismatched,json).get("review_prompts").toString().contains("YoY -10.00%"));
  var stale=new LinkedHashMap<String,Object>(quarter);stale.put("latest_period","2020-03-31");
  var staleHolding=new LinkedHashMap<>(holding);staleHolding.put("thesis_evidence",Map.of("company_evidence",Map.of("isin","INE002A01018","quarterly_financials",stale)));
  assertFalse(PortfolioThesisSummary.summarize(staleHolding,json).get("review_prompts").toString().contains("YoY -10.00%"));
 }
 @Test void independentGovernanceIsExactCompanyEvidenceNotClearance(){
  var pledge=Map.of("isin","INE002A01018","status","REPORTED_QUARTERLY_AGGREGATE","period","2026-09-30","source_url","https://nsearchives.nseindia.com/filing");
  var filing=Map.of("isin","INE002A01018","status","REPORTED_CONSOLIDATED_FILING","period","2026-09-30");
  var governance=Map.of("isin","INE002A01018","findings",List.of("ISSUER_REPORTED_PROMOTER_PLEDGE_REVIEW","ISSUER_REPORTED_AUDIT_QUALIFICATION_REVIEW","UNRECOGNIZED"),"independent_pledge_evidence",pledge,"independent_financial_evidence",filing);
  var holding=Map.<String,Object>of("asset_type","EQUITY","isin","INE002A01018","thesis_evidence",Map.of("governance_review",governance));
  var report=PortfolioThesisSummary.summarize(holding,json);
  assertTrue(report.get("review_prompts").toString().contains("pledged promoter shares"));
  assertTrue(report.get("review_prompts").toString().contains("audit qualification"));
  assertFalse(report.get("review_prompts").toString().contains("UNRECOGNIZED"));
  assertEquals("REVIEW_EVIDENCE",report.get("status"));
  var wrong=new LinkedHashMap<>(holding);wrong.put("isin","INE009A01021");
  assertEquals("INSUFFICIENT_FOR_VERDICT",PortfolioThesisSummary.summarize(wrong,json).get("status"));
 }
}
