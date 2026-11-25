package com.trading.market;

import java.math.*;
import java.util.*;

/** One-time turnover cost sensitivity, not a tariff, tax calculation or order. */
final class PortfolioRebalancingCosts {
  private PortfolioRebalancingCosts(){}
  private static final BigDecimal BPS=BigDecimal.valueOf(10000),HUNDRED=BigDecimal.valueOf(100);
  private static final List<Integer> RATES=List.of(10,50,100);
  record Case(String label,BigDecimal purchases,BigDecimal sales){}
  record Estimate(int basisPointsPerSide,BigDecimal hypotheticalCost,BigDecimal costPercentOfRecordedValue,
    BigDecimal additionalCashIncludingCost){}
  record Row(String label,BigDecimal purchaseNotional,BigDecimal saleNotional,BigDecimal grossNotional,
    BigDecimal additionalCashBeforeCost,List<Estimate> estimates){}
  static Map<String,Object> assess(BigDecimal recordedValue,List<Case> cases){
    var out=new LinkedHashMap<String,Object>();
    out.put("notice","Illustrative one-time costs at 10, 50 and 100 basis points on each purchase and sale notional. These are assumptions, not actual broker charges, tax rates, exit loads or execution prices. Extra cash preserves the pre-cost hypothetical target amounts; no automatic cash deduction or trade. Taxes, fixed charges, liquidity, lot sizes and ongoing fund expenses are excluded. Historical NAVs already reflect fund expenses; do not deduct TER again.");
    out.put("basis_points_per_side",RATES);
    out.put("scenarios",List.of());
    if(recordedValue==null||recordedValue.signum()<=0||cases.isEmpty()||
        cases.stream().anyMatch(c->c.purchases()==null||c.sales()==null||c.sales().signum()<0||
          c.purchases().compareTo(c.sales())<0||c.sales().compareTo(recordedValue)>0)){
      out.put("status","INSUFFICIENT_TURNOVER_EVIDENCE");return out;
    }
    List<Row> rows=new ArrayList<>();
    for(Case c:cases){
      BigDecimal buy=money(c.purchases()),sell=money(c.sales()),gross=buy.add(sell),cash=buy.subtract(sell);
      List<Estimate> estimates=new ArrayList<>();
      for(int rate:RATES){
        BigDecimal cost=money(gross.multiply(BigDecimal.valueOf(rate)).divide(BPS));
        estimates.add(new Estimate(rate,cost,cost.multiply(HUNDRED).divide(recordedValue,4,RoundingMode.HALF_UP),cash.add(cost)));
      }
      rows.add(new Row(c.label(),buy,sell,gross,cash,estimates));
    }
    out.put("status","ILLUSTRATIVE_COST_SENSITIVITY");out.put("scenarios",rows);
    return out;
  }
  private static BigDecimal money(BigDecimal v){return v.setScale(2,RoundingMode.HALF_UP);}
}
