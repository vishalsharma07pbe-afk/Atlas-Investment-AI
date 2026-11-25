package com.trading.market;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PortfolioSaleResearchTest {
  private static final LocalDate TODAY=LocalDate.of(2026,11,25);
  private final ObjectMapper json=new ObjectMapper();
  private BigDecimal n(String value){return new BigDecimal(value);}
  private Map<String,Object> holding(String symbol,String isin,String units,String price,String cost){
    return Map.of("symbol",symbol,"isin",isin,"asset_type","EQUITY","exchange","NSE","quantity",n(units),
      "last_price",n(price),"market_value",n(units).multiply(n(price)),"invested",n(cost),"recorded_valuation_recent",true);
  }
  private Map<String,Object> buy(String symbol,int age,String units,String price){
    return Map.of("symbol",symbol,"asset_type","EQUITY","transaction_type","BUY",
      "transaction_date",TODAY.minusDays(age),"quantity",n(units),"unit_price",n(price),"cash_amount",n(units).multiply(n(price)));
  }
  private static final String A="INE002A01018",B="INE009A01021";
  private List<Map<String,Object>> holdings(){return List.of(holding("A",A,"8","100","580"),holding("B",B,"2","100","240"));}
  private List<Map<String,Object>> trades(){return List.of(buy("A",400,"2","50"),buy("A",100,"6","80"),buy("B",150,"2","120"));}
  private Map<String,Object> alternative(String kind,int a,int b){
    return Map.of("kind",kind,"weights",List.of(Map.of("isin",A,"weightPercent",a),Map.of("isin",B,"weightPercent",b)));
  }
  private Map<String,Object> report(List<Map<String,Object>> holdings,List<Map<String,Object>> trades){
    return Map.of("journal_lot_reconciliation",PortfolioJournalLots.assess(holdings,trades,TODAY),
      "diversification",Map.of("allocation_research",Map.of("status","HYPOTHETICAL_SCENARIOS_AVAILABLE","recorded_value",1000,
        "scenarios",List.of(Map.of("hypotheticalNewIdentities",5,"hypotheticalRedistributedCapital",750)))),
      "equity_correlation",Map.of("historical_allocation",Map.of("status","HISTORICAL_COMPARISON_AVAILABLE",
        "direct_equity_value",1000,"alternatives",List.of(alternative("CURRENT_WEIGHTS",80,20),alternative("EQUAL_WEIGHTS",50,50)))));
  }
  private List<PortfolioSaleResearch.Scenario> scenarios(List<Map<String,Object>> holdings,List<Map<String,Object>> trades){
    return ((List<?>)PortfolioSaleResearch.assess(holdings,report(holdings,trades),json,TODAY).get("scenarios")).stream()
      .map(PortfolioSaleResearch.Scenario.class::cast).toList();
  }
  private void equal(String expected,BigDecimal actual){assertEquals(0,n(expected).compareTo(actual));}
  @Test void usesEarlierLotsRatherThanAverageCostAndPreservesLosses(){
    var scenarios=scenarios(holdings(),trades());
    var redistribution=scenarios.getFirst();
    assertEquals("PROVISIONAL_SALE_EVIDENCE",redistribution.status());
    equal("750",redistribution.grossProceeds());equal("600",redistribution.provisionalOpenCost());
    equal("150",redistribution.grossGainOrLoss());
    equal("-30",redistribution.sales().get(1).grossGainOrLoss());
    var baseline=scenarios.get(1);
    assertEquals("NO_HYPOTHETICAL_SALE",baseline.status());equal("0",baseline.grossGainOrLoss());
    var equalWeight=scenarios.get(2);
    equal("300",equalWeight.grossProceeds());equal("180",equalWeight.provisionalOpenCost());equal("120",equalWeight.grossGainOrLoss());
    assertEquals(100,equalWeight.sales().getFirst().youngestCalendarDays());
    assertEquals(400,equalWeight.sales().getFirst().oldestCalendarDays());
    assertEquals("CONDITIONAL_REFERENCE_ONLY",equalWeight.taxReference().status());
    equal("20",equalWeight.taxReference().shortPositiveGains());
    equal("100",equalWeight.taxReference().longPositiveGains());
    equal("4",equalWeight.taxReference().baseTaxIfFullThresholdUnused());
    equal("16.5",equalWeight.taxReference().baseTaxIfThresholdAlreadyUsed());
  }
  @Test void missingSoldLotsWithholdTotalsButNonSoldLotsAreNotRequired(){
    var scenarios=scenarios(holdings(),trades().subList(0,2));
    assertEquals("INSUFFICIENT_SALE_EVIDENCE",scenarios.getFirst().status());
    assertNull(scenarios.getFirst().grossGainOrLoss());
    assertTrue(scenarios.getFirst().sales().isEmpty());
    assertEquals("PROVISIONAL_SALE_EVIDENCE",scenarios.get(2).status());
  }
  @Test void duplicateExactIdentityWithholdsResearch(){
    var h=List.of(holding("A",A,"8","100","580"),holding("B",A,"2","100","240"));
    var scenarios=scenarios(h,trades());
    assertTrue(scenarios.stream().allMatch(s->"INSUFFICIENT_SALE_EVIDENCE".equals(s.status())));
  }
}
