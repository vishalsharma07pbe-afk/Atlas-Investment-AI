package com.trading.market;

import java.math.BigDecimal;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PortfolioRebalancingCostsTest {
  private BigDecimal money(String value){return new BigDecimal(value);}
  private void amount(String value,BigDecimal actual){assertEquals(0,money(value).compareTo(actual));}
  private PortfolioRebalancingCosts.Row row(Map<String,Object> report,int index){
    return (PortfolioRebalancingCosts.Row)((List<?>)report.get("scenarios")).get(index);
  }
  @Test void equalBuysAndSalesChargeBothSidesWithoutDoubleCountingCash(){
    var result=PortfolioRebalancingCosts.assess(money("100000"),List.of(
      new PortfolioRebalancingCosts.Case("Redistribution",money("30000"),money("30000"))));
    assertEquals("ILLUSTRATIVE_COST_SENSITIVITY",result.get("status"));
    var r=row(result,0);
    amount("60000",r.grossNotional());amount("0",r.additionalCashBeforeCost());
    var mid=r.estimates().get(1);
    assertEquals(50,mid.basisPointsPerSide());
    amount("300",mid.hypotheticalCost());amount("0.3",mid.costPercentOfRecordedValue());
    amount("300",mid.additionalCashIncludingCost());
  }
  @Test void cashOnlyContributionChargesPurchasesAndPreservesTargetAmounts(){
    var report=PortfolioRebalancingCosts.assess(money("5000"),List.of(
      new PortfolioRebalancingCosts.Case("Contribution",money("2000"),BigDecimal.ZERO),
      new PortfolioRebalancingCosts.Case("No change",BigDecimal.ZERO,BigDecimal.ZERO)));
    var r=row(report,0);
    amount("2000",r.grossNotional());amount("2000",r.additionalCashBeforeCost());
    amount("10",r.estimates().get(1).hypotheticalCost());
    amount("2010",r.estimates().get(1).additionalCashIncludingCost());
    amount("0",row(report,1).estimates().get(2).hypotheticalCost());
  }
  @Test void invalidTurnoverIsWithheld(){
    assertEquals("INSUFFICIENT_TURNOVER_EVIDENCE",PortfolioRebalancingCosts.assess(money("100"),List.of(
      new PortfolioRebalancingCosts.Case("Invalid",money("200"),money("200")))).get("status"));
    assertEquals("INSUFFICIENT_TURNOVER_EVIDENCE",PortfolioRebalancingCosts.assess(money("100"),List.of(
      new PortfolioRebalancingCosts.Case("Invalid",money("10"),money("20")))).get("status"));
  }
}
