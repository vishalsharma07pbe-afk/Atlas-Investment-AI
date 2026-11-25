package com.trading.market;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PortfolioDiversificationTest {
 private final ObjectMapper json=new ObjectMapper();
 private static Map<String,Object> equity(String symbol,String isin,int value,String sector){
  var h=new HashMap<String,Object>();
  h.put("asset_type","EQUITY");h.put("symbol",symbol);h.put("isin",isin);
  h.put("recorded_market_value",BigDecimal.valueOf(value));
  if(sector!=null)h.put("thesis_evidence",Map.of("company_evidence",Map.of("isin",isin,"sections",Map.of("profile",Map.of("data",Map.of("sector",sector))))));
  return h;
 }
 @Test void aggregatesDuplicateIsinsAndKeepsUnknownClassificationInDenominator(){
  var rows=List.of(equity("FIRST","INE002A01018",30,"Energy"),equity("SECOND","INE002A01018",20,null),
   equity("THIRD","INE009A01021",25,null),
   Map.<String,Object>of("asset_type","MUTUAL_FUND","symbol","123456","exact_scheme_code",123456,"scheme_category","Large Cap","recorded_market_value",BigDecimal.valueOf(25)));
  var result=PortfolioDiversification.summarize(rows,json);
  assertEquals("PARTIAL_COVERAGE",result.get("status"));
  assertEquals(3,result.get("resolved_identity_count"));
  assertEquals(new BigDecimal("66.67"),result.get("sector_coverage_percent"));
  assertEquals(new BigDecimal("100.00"),result.get("fund_category_coverage_percent"));
  assertEquals(new BigDecimal("100.00"),result.get("top_three_resolved_weight_percent"));
  assertTrue(result.get("review_prompts").toString().contains("exceeds 25%"));
  assertTrue(result.get("direct_equity_sector_exposure").toString().contains("Unknown"));
 }
 @Test void missingValuesAndUnresolvedFundDoNotImplyDiversification(){
  var result=PortfolioDiversification.summarize(List.of(
   Map.of("asset_type","EQUITY","symbol","MISSING"),
   Map.of("asset_type","MUTUAL_FUND","symbol","123456","recorded_market_value",100)),json);
  assertEquals(1,result.get("unpriced_count"));assertEquals(1,result.get("unresolved_identity_count"));
  assertEquals(0,result.get("resolved_identity_count"));
  assertEquals("PARTIAL_COVERAGE",result.get("status"));
 }
 @Test void conflictingClassificationsAreUnknown(){
  var result=PortfolioDiversification.summarize(List.of(equity("A","INE002A01018",50,"Energy"),equity("B","INE002A01018",50,"Finance")),json);
  assertEquals(new BigDecimal("0.00"),result.get("sector_coverage_percent"));
 }
 @Test void automaticAllocationUsesAggregatedIdentitiesAndRecentValuations(){
  var first=equity("FIRST","INE002A01018",60,"Energy");
  var duplicate=equity("SECOND","INE002A01018",40,"Energy");
  first.put("recorded_valuation_recent",true);duplicate.put("recorded_valuation_recent",true);
  var rows=List.of(first,duplicate);
  var result=PortfolioDiversification.summarize(rows,json);
  var plan=(Map<?,?>)result.get("allocation_research");
  assertEquals("HYPOTHETICAL_SCENARIOS_AVAILABLE",plan.get("status"));
  assertEquals(0,new BigDecimal("100").compareTo((BigDecimal)plan.get("current_largest_percent")));
  duplicate.put("recorded_valuation_recent",false);
  var stale=(Map<?,?>)PortfolioDiversification.summarize(rows,json).get("allocation_research");
  assertEquals("INSUFFICIENT_RECENT_EXACT_VALUATIONS",stale.get("status"));
 }

 @Test void stressAggregatesDuplicateExactIdentitiesAndWithholdsIncompleteValuations(){
  var first=equity("FIRST","INE002A01018",60,"Energy");
  var duplicate=equity("SECOND","INE002A01018",40,"Energy");
  first.put("recorded_valuation_recent",true);duplicate.put("recorded_valuation_recent",true);
  var rows=List.of(first,duplicate);
  var stress=(Map<?,?>)PortfolioDiversification.summarize(rows,json).get("exposure_stress");
  assertEquals("HYPOTHETICAL_SCENARIOS_AVAILABLE",stress.get("status"));
  var largest=((List<?>)stress.get("scenarios")).stream().map(PortfolioExposureStress.Scenario.class::cast)
    .filter(s->"LARGEST_IDENTITY_SHOCK".equals(s.kind())).findFirst().orElseThrow();
  assertEquals(0,new BigDecimal("-30").compareTo(largest.changeAmount()));
  duplicate.put("recorded_valuation_recent",false);
  assertEquals("INSUFFICIENT_RECENT_VALUATIONS",((Map<?,?>)PortfolioDiversification.summarize(rows,json).get("exposure_stress")).get("status"));
 }

}
