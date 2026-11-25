package com.trading.market;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class PortfolioCrossAssetAllocationTest {
  private static final LocalDate TODAY=LocalDate.of(2026,11,25);
  private static final String EQUITY="INE002A01018",FUND="AMFI:123456";
  private List<Map<String,Object>> history(String source,int count){
    List<Map<String,Object>> rows=new ArrayList<>();
    double value=100;
    for(int i=0;i<count;i++){
      value*=1+(i%2==0?0.01:-0.01);
      rows.add(new HashMap<>(Map.of("nav_date",TODAY.minusDays(count-i),"nav",value,"source_code",source)));
    }
    return rows;
  }
  @Test void navSourceIsNotSplicedAcrossObservations(){
    var rows=history("MFAPI",40);
    rows.getLast().put("source_code","AMFI");
    var nav=PortfolioCrossAssetAllocation.navReturns(rows,TODAY);
    assertNotNull(nav);
    assertEquals("MFAPI",nav.source());
    assertEquals(38,nav.returns().size());
    for(int i=0;i<20;i++)rows.get(i).put("source_code","AMFI");
    assertNull(PortfolioCrossAssetAllocation.navReturns(rows,TODAY));
  }
  @Test void rejectsDuplicateDatesAndStaleNav(){
    var rows=history("AMFI",40);
    rows.add(new HashMap<>(rows.getFirst()));
    assertNull(PortfolioCrossAssetAllocation.navReturns(rows,TODAY));
    rows=history("AMFI",40);
    for(var row:rows)row.put("nav_date",((LocalDate)row.get("nav_date")).minusDays(6));
    assertNull(PortfolioCrossAssetAllocation.navReturns(rows,TODAY));
  }
  @Test void mixedComparisonUsesCommonIntervalsAndDistinctSchemeIdentities(){
    var nav=PortfolioCrossAssetAllocation.navReturns(history("AMFI",41),TODAY);
    assertNotNull(nav);
    var equities=new HashMap<PortfolioEquityCorrelation.Interval,Double>();
    nav.returns().forEach((d,v)->equities.put(d,-v));
    var report=PortfolioHistoricalAllocation.assessMixed(
      Map.of(EQUITY,new BigDecimal("800"),FUND,new BigDecimal("200")),Map.of(EQUITY,"STOCK",FUND,"123456"),
      Map.of(EQUITY,equities,FUND,nav.returns()),TODAY,true);
    assertEquals("HISTORICAL_COMPARISON_AVAILABLE",report.get("status"));
    assertEquals(40,report.get("observations"));
    assertEquals("EQUAL_WEIGHTS",report.get("lowest_observed_variability"));
    var json=new com.fasterxml.jackson.databind.ObjectMapper().valueToTree(report);
    var equal=json.path("alternatives").get(2);
    assertEquals(0,equal.path("sampleVolatilityPercent").asDouble(),1e-9);
    assertEquals(30,equal.path("oneWayTurnoverPercent").asDouble(),1e-9);
    assertTrue(equal.path("weights").get(0).has("identity"));
    equities.keySet().removeIf(d->d.end().isBefore(TODAY.minusDays(20)));
    assertEquals("INSUFFICIENT_COMMON_RETURN_INTERVALS",PortfolioHistoricalAllocation.assessMixed(
      Map.of(EQUITY,BigDecimal.ONE,FUND,BigDecimal.ONE),Map.of(),
      Map.of(EQUITY,equities,FUND,nav.returns()),TODAY,true).get("status"));
  }
  @Test void incompleteExactHoldingsAreWithheldBeforeNavQueries(){
    JdbcTemplate jdbc=mock(JdbcTemplate.class);
    var equity=Map.<String,Object>of("asset_type","EQUITY","market_value",BigDecimal.TEN,
      "recorded_valuation_recent",true,"isin",EQUITY,"instrument_id",1L,"symbol","TEST");
    var fund=Map.<String,Object>of("asset_type","MUTUAL_FUND","market_value",BigDecimal.TEN,
      "recorded_valuation_recent",true,"symbol","UNRESOLVED");
    assertEquals("INSUFFICIENT_RECENT_EXACT_MIXED_COVERAGE",
      PortfolioCrossAssetAllocation.collect(jdbc,List.of(equity,fund),Map.of(),TODAY).get("status"));
    assertEquals("NO_MIXED_POSITIVE_HOLDINGS",
      PortfolioCrossAssetAllocation.collect(jdbc,List.of(equity),Map.of(),TODAY).get("status"));
    verifyNoInteractions(jdbc);
  }
}
