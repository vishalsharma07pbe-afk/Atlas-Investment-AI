package com.trading.market;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PortfolioOpportunityContextTest {
 private final ObjectMapper json=new ObjectMapper();
 private static Map<String,Object> candidate(String isin){
  return Map.of("isin",isin,"symbol","TEST","exchange","NSE","sector","Energy","evidence_type","TECHNICAL_WATCH_ONLY","horizon","LONG_TERM");
 }
 @Test void excludesHeldAcrossExchangesAndKeepsSectorContext(){
  List<Map<String,Object>> holdings=List.of(
   Map.of("asset_type","EQUITY","isin","INE002A01018","exchange","BSE"),
   Map.of("asset_type","EQUITY","symbol","UNRESOLVED"));
  var exposure=Map.<String,Object>of("direct_equity_sector_exposure",List.of(Map.of("label","energy","weight_percent",55)));
  var snapshot=json.valueToTree(Map.of("status","WATCH_EVIDENCE_AVAILABLE","equities",
    List.of(candidate("INE002A01018"),candidate("INE009A01021"))));
  var result=PortfolioOpportunityContext.compare(holdings,exposure,snapshot,json);
  assertEquals(1,result.get("held_excluded_count"));
  var equities=(List<?>)result.get("equities");
  assertEquals(1,equities.size());
  var item=(Map<?,?>)equities.getFirst();
  assertEquals("EXISTING_SECTOR_CONCENTRATION",item.get("context"));
  assertEquals("UNRESOLVED_HOLDINGS_EXIST",item.get("identity_status"));
  assertEquals("TECHNICAL_WATCH_ONLY",item.get("evidence_type"));
 }
 @Test void excludesExactHeldSchemeAndPreservesHistoricalStatus(){
  List<Map<String,Object>> holdings=List.of(Map.of("asset_type","MUTUAL_FUND","symbol","123456",
     "exact_scheme_code",123456,"scheme_category","Open Ended Schemes (Equity Scheme - Large Cap Fund)"));
  var fund=Map.<String,Object>of("scheme_code","123456","name","Example","category","LARGE_CAP","evidence_type","HISTORICAL_WATCH_ONLY");
  var second=new HashMap<>(fund);second.put("scheme_code","123457");
  var result=PortfolioOpportunityContext.compare(holdings,Map.of(),json.valueToTree(Map.of("status","WATCH_EVIDENCE_AVAILABLE","funds",List.of(fund,second))),json);
  assertEquals(1,result.get("held_excluded_count"));
  var item=(Map<?,?>)((List<?>)result.get("funds")).getFirst();
  assertEquals("EXISTING_FUND_CATEGORY",item.get("context"));
  assertEquals("HISTORICAL_WATCH_ONLY",item.get("evidence_type"));
 }
 @Test void unavailablePublicDataDoesNotInventOpportunity(){
  var result=PortfolioOpportunityContext.compare(List.of(),Map.of(),json.createObjectNode(),json);
  assertEquals("UNAVAILABLE",result.get("status"));
  assertTrue(((List<?>)result.get("equities")).isEmpty());
 }
 @Test void matchedAlternativeRequiresIdenticalDatesAndHigherObservedReturn(){
  var heldWindow=Map.of("first_date","2026-08-25","last_date","2026-11-23","dates_digest","a".repeat(64),"stock_return_percent",3);
  var holding=Map.<String,Object>of("asset_type","EQUITY","isin","INE002A01018","exchange","NSE","symbol","HELD","holding_relative_strength",Map.of("windows",Map.of("60",heldWindow)));
  var watch=new LinkedHashMap<>(candidate("INE009A01021"));watch.put("adjustment_status","ADJUSTED");
  var other=Map.of("first_date","2026-08-25","last_date","2026-11-23","dates_digest","a".repeat(64),"return_percent",5);
  watch.put("matched_60",other);
  var report=PortfolioOpportunityContext.compare(List.of(holding),Map.of(),json.valueToTree(Map.of("equities",List.of(watch))),json);
  assertEquals(1,((List<?>)report.get("matched_comparisons")).size());
  watch.put("matched_60",Map.of("first_date","2026-08-25","last_date","2026-11-23","dates_digest","b".repeat(64),"return_percent",5));
  assertTrue(((List<?>)PortfolioOpportunityContext.compare(List.of(holding),Map.of(),json.valueToTree(Map.of("equities",List.of(watch))),json).get("matched_comparisons")).isEmpty());
 }
}
