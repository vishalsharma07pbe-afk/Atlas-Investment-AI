package com.trading.market;

import java.math.BigDecimal;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PortfolioRebalancingFundingTest {
  private BigDecimal n(String s){return new BigDecimal(s);}
  private void eq(String expected,BigDecimal actual){assertEquals(0,n(expected).compareTo(actual));}
  private PortfolioRebalancingCosts.Row cost(String label,String buy,String sell){
    var report=PortfolioRebalancingCosts.assess(n("100000"),List.of(
      new PortfolioRebalancingCosts.Case(label,n(buy),n(sell))));
    return (PortfolioRebalancingCosts.Row)((List<?>)report.get("scenarios")).getFirst();
  }
  private PortfolioSaleResearch.Scenario sale(String scope,String asset,String gross){
    var position=new PortfolioSaleResearch.Sale("ID","TEST",asset,n("10"),n(gross),n("100"),n(gross).subtract(n("100")),100,400);
    var tax=new PortfolioEquityTaxReference.Reference("CONDITIONAL_REFERENCE_ONLY","2026-27",n("100"),n("0"),n("1000"),n("0"),n("20"),n("145"),List.of());
    return new PortfolioSaleResearch.Scenario(scope,"EQUAL_WEIGHTS","PROVISIONAL_SALE_EVIDENCE",n(gross),n("100"),n(gross).subtract(n("100")),List.of(position),List.of(),tax);
  }
  @Test void equityReferenceAddsChargesWithoutDeductingTargetAmounts(){
    var row=cost("EQUAL_WEIGHTS","10000","10000");
    var c=PortfolioRebalancingFunding.compare("DIRECT_EQUITY_ALLOCATION","EQUAL_WEIGHTS",row,
      sale("DIRECT_EQUITY_ALLOCATION","EQUITY","10000"),null);
    assertEquals("CONDITIONAL_COMPONENTS_AVAILABLE",c.status());
    eq("0",c.conditionalExitLoad());
    var e=c.estimates().get(1);
    eq("100",e.transactionCost());eq("100",e.additionalCashIncludingTransactionCost());
    eq("120",e.conditionalCashIfThresholdUnused());eq("245",e.conditionalCashIfThresholdUsed());
  }
  @Test void fundTaxIsNotInferredEvenWhenCurrentExitLoadIsAvailable(){
    var load=new PortfolioFundExitLoad.Scenario("MIXED_ALLOCATION","EQUAL_WEIGHTS","CONDITIONAL_CURRENT_TERMS",n("25"),List.of());
    var c=PortfolioRebalancingFunding.compare("MIXED_ALLOCATION","EQUAL_WEIGHTS",cost("EQUAL_WEIGHTS","10000","10000"),
      sale("MIXED_ALLOCATION","MUTUAL_FUND","10000"),load);
    assertEquals("PARTIAL_COMPONENTS",c.status());
    eq("125",c.estimates().get(1).additionalCashWithKnownExitLoad());
    assertNull(c.estimates().get(1).conditionalCashIfThresholdUnused());
    assertNull(c.conditionalTaxIfThresholdUsed());
    assertTrue(c.evidenceGaps().stream().anyMatch(g->g.contains("Fund tax classification")));
  }
  @Test void missingOrMismatchedSaleEvidenceWithholdsCombinedAmounts(){
    var row=cost("EQUAL_WEIGHTS","10000","10000");
    for(var s:Arrays.asList(null,sale("DIRECT_EQUITY_ALLOCATION","EQUITY","9000"))){
      var c=PortfolioRebalancingFunding.compare("DIRECT_EQUITY_ALLOCATION","EQUAL_WEIGHTS",row,s,null);
      assertEquals("PARTIAL_COMPONENTS",c.status());
      eq("100",c.estimates().get(1).additionalCashIncludingTransactionCost());
      assertNull(c.estimates().get(1).additionalCashWithKnownExitLoad());
      assertNull(c.estimates().get(1).conditionalCashIfThresholdUsed());
    }
  }
  @Test void joinsNoSaleContributionSeparatelyFromFixedCapitalRedistribution(){
    var report=Map.<String,Object>of("diversification",Map.of("allocation_research",
      PortfolioAllocationResearch.assess(List.of(n("1000")),n("1000"),true)));
    var result=PortfolioRebalancingFunding.assess(report);
    var rows=((List<?>)result.get("comparisons")).stream().map(PortfolioRebalancingFunding.Comparison.class::cast).toList();
    assertEquals(4,rows.size());
    var contribution=rows.getFirst();
    assertEquals("CONCENTRATION_CONTRIBUTION",contribution.scope());
    assertEquals("5 new identities",contribution.kind());
    eq("3015",contribution.estimates().get(1).conditionalCashIfThresholdUsed());
    assertEquals("CONCENTRATION_REDISTRIBUTION",rows.get(1).scope());
    assertNull(rows.get(1).estimates().get(1).conditionalCashIfThresholdUsed());
  }
}
