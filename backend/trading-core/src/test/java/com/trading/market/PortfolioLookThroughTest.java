package com.trading.market;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Instant;
import java.math.BigDecimal;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PortfolioLookThroughTest {
  private final ObjectMapper json=new ObjectMapper();
  private final Instant now=Instant.parse("2026-11-25T10:00:00Z");
  private static final String A="INE002A01018",B="INE009A01021";
  private Map<String,Object> direct(int value){
    return Map.of("asset_type","EQUITY","isin",A,"recorded_market_value",value,"recorded_valuation_recent",true);
  }
  private Map<String,Object> fund(String code,String fundId,int value,String day,int a,int b){
    var disclosure=Map.of("source","TIGZIG_AMFI_DERIVED","scheme_code",code,"fund_id",fundId,
      "isin","INF179K01BB2","plan","DIRECT","collected_at",now.toString());
    var portfolio=Map.of("source","TIGZIG_AMC_DERIVED","status","SECONDARY_COMPOSITION_ONLY",
      "scheme_code",code,"fund_id",fundId,"collected_at",now.toString(),"portfolio_date",day,
      "exact_equity_weights",Map.of(A,a,B,b),"exact_equity_count",2,
      "exact_listed_equity_weight_percent",a+b,"reported_weight_total_percent",100);
    return Map.of("asset_type","MUTUAL_FUND","symbol",code,"exact_scheme_code",Integer.parseInt(code),
      "recorded_market_value",value,"recorded_valuation_recent",true,
      "fund_thesis_evidence",Map.of("status","SECONDARY_REPORTED_EVIDENCE","disclosure",disclosure,"portfolio",portfolio));
  }
  @Test void combinesDirectAndIndirectWithoutNormalizingOrCountingFundUnitsTwice(){
    var rows=List.of(direct(200),fund("123456","fund:a",500,"2026-10-31",60,20),
      fund("123457","fund:b",300,"2026-10-31",30,60));
    var result=json.valueToTree(PortfolioLookThrough.assess(rows,json,now));
    assertEquals("DATED_PARTIAL_EQUITY_EXPOSURE_ESTIMATE",result.path("status").asText());
    assertEquals(87.0,result.path("mapped_portfolio_percent").asDouble());
    assertEquals(130.0,result.path("unmodeled_value").asDouble());
    var largest=result.path("exposures").get(0);
    assertEquals(A,largest.path("isin").asText());
    assertEquals(200.0,largest.path("directValue").asDouble());
    assertEquals(390.0,largest.path("indirectValue").asDouble());
    assertEquals(590.0,largest.path("estimatedValue").asDouble());
    assertEquals(59.0,largest.path("portfolioPercent").asDouble());
    assertEquals(50.0,result.path("overlap_pairs").get(0).path("sharedWeightPercent").asDouble());
    assertEquals(3,result.path("risk_observation_count").asInt());
    assertEquals(2,java.util.stream.StreamSupport.stream(result.path("risk_observations").spliterator(),false)
      .filter(n->"HIDDEN_EQUITY_CONCENTRATION".equals(n.path("kind").asText())).count());
    assertEquals(1,java.util.stream.StreamSupport.stream(result.path("risk_observations").spliterator(),false)
      .filter(n->"HIGH_FUND_OVERLAP".equals(n.path("kind").asText())).count());
  }
  @Test void excludesDifferentDatesAndReportsUnmodeledCapital(){
    var rows=List.of(direct(200),fund("123456","fund:a",500,"2026-10-31",60,20),
      fund("123457","fund:b",300,"2026-09-30",30,60));
    var result=json.valueToTree(PortfolioLookThrough.assess(rows,json,now));
    assertEquals(62.5,result.path("matched_fund_value_percent").asDouble());
    assertEquals(60.0,result.path("mapped_portfolio_percent").asDouble());
    assertEquals(0,result.path("overlap_pairs").size());
  }
  @Test void aggregatesDuplicateSchemeHoldingsAndFlagsSharedUnderlyingFund(){
    var rows=List.of(fund("123456","fund:a",250,"2026-10-31",60,20),
      fund("123456","fund:a",250,"2026-10-31",60,20),
      fund("123457","fund:a",500,"2026-10-31",60,20));
    var result=json.valueToTree(PortfolioLookThrough.assess(rows,json,now));
    assertEquals(2,result.path("matched_scheme_count").asInt());
    assertEquals(80.0,result.path("mapped_portfolio_percent").asDouble());
    assertTrue(result.path("overlap_pairs").get(0).path("sameUnderlyingFund").asBoolean());
  }
  @Test void missingAndStaleEvidenceDoesNotImplyZeroOverlap(){
    var stale=fund("123456","fund:a",500,"2026-08-31",60,20);
    assertEquals("NO_MATCHED_FUND_COMPOSITION",PortfolioLookThrough.assess(List.of(stale),json,now).get("status"));
    var aged=new HashMap<>(direct(200));aged.put("recorded_valuation_recent",false);
    assertEquals("INSUFFICIENT_RECENT_VALUATIONS",PortfolioLookThrough.assess(List.of(aged,stale),json,now).get("status"));
  }
  @Test void doesNotRepeatAlreadyVisibleDirectConcentrationOrFlagExactThreshold(){
    var result=json.valueToTree(PortfolioLookThrough.assess(List.of(direct(500),
      fund("123456","fund:a",500,"2026-10-31",30,50)),json,now));
    assertEquals(0,result.path("risk_observation_count").asInt());
  }
  @Test void noSameDatePairDoesNotImplyHighOverlap(){
    var result=json.valueToTree(PortfolioLookThrough.assess(List.of(direct(200),
      fund("123456","fund:a",500,"2026-10-31",60,20),
      fund("123457","fund:b",300,"2026-09-30",30,60)),json,now));
    assertFalse(java.util.stream.StreamSupport.stream(result.path("risk_observations").spliterator(),false)
      .anyMatch(n->"HIGH_FUND_OVERLAP".equals(n.path("kind").asText())));
  }

}
