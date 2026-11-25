package com.trading.market;

import java.math.*;
import java.util.*;

/** Joins existing local hypothetical evidence without treating unknown costs as zero. */
final class PortfolioRebalancingFunding {
  private PortfolioRebalancingFunding(){}
  private static final BigDecimal ZERO=BigDecimal.ZERO;
  record Estimate(int basisPointsPerSide,BigDecimal transactionCost,
      BigDecimal additionalCashIncludingTransactionCost,BigDecimal additionalCashWithKnownExitLoad,
      BigDecimal conditionalCashIfThresholdUnused,BigDecimal conditionalCashIfThresholdUsed){}
  record Comparison(String scope,String kind,String status,BigDecimal purchaseNotional,
      BigDecimal saleNotional,BigDecimal additionalCashBeforeCost,BigDecimal conditionalExitLoad,
      BigDecimal conditionalTaxIfThresholdUnused,BigDecimal conditionalTaxIfThresholdUsed,
      List<Estimate> estimates,List<String> evidenceGaps){}
  private record Key(String scope,String kind){}

  static Map<String,Object> assess(Map<String,Object> review){
    Map<Key,PortfolioSaleResearch.Scenario> sales=new HashMap<>();
    if(review.get("sale_research") instanceof Map<?,?> sale&&sale.get("scenarios") instanceof List<?> list)
      for(Object item:list)if(item instanceof PortfolioSaleResearch.Scenario s)sales.put(new Key(s.scope(),s.kind()),s);
    Map<Key,PortfolioFundExitLoad.Scenario> loads=new HashMap<>();
    if(review.get("fund_exit_load_research") instanceof Map<?,?> exit&&exit.get("scenarios") instanceof List<?> list)
      for(Object item:list)if(item instanceof PortfolioFundExitLoad.Scenario s)loads.put(new Key(s.scope(),s.kind()),s);
    List<Comparison> comparisons=new ArrayList<>();
    if(review.get("diversification") instanceof Map<?,?> div&&div.get("allocation_research") instanceof Map<?,?> a)
      append(a,"CONCENTRATION_REDISTRIBUTION",sales,loads,comparisons);
    if(review.get("equity_correlation") instanceof Map<?,?> correlation){
      if(correlation.get("historical_allocation") instanceof Map<?,?> a)
        append(a,"DIRECT_EQUITY_ALLOCATION",sales,loads,comparisons);
      if(correlation.get("cross_asset_allocation") instanceof Map<?,?> a)
        append(a,"MIXED_ALLOCATION",sales,loads,comparisons);
    }
    return Map.of("status",comparisons.isEmpty()?"NO_ALLOCATION_SCENARIOS":"FUNDING_COMPARISONS_AVAILABLE",
      "comparisons",comparisons,"notice","Conditional extra cash to preserve pre-cost hypothetical target amounts, not an executable allocation or tax liability. Generic per-side transaction charges exclude the separate exit load and base tax reference. Tax assumptions, losses, annual income and gains, surcharge, cess, actual tariffs, scheme terms, settlement and available capital are not verified. Combined amounts are withheld when a required component is unknown; no-sale scenarios have no disposal-related tax or exit load. Compare the scenarios separately; do not add their costs.");
  }
  private static void append(Map<?,?> allocation,String scope,Map<Key,PortfolioSaleResearch.Scenario> sales,
      Map<Key,PortfolioFundExitLoad.Scenario> loads,List<Comparison> out){
    if(!(allocation.get("cost_sensitivity") instanceof Map<?,?> costs)||
      !"ILLUSTRATIVE_COST_SENSITIVITY".equals(costs.get("status"))||
      !(costs.get("scenarios") instanceof List<?> rows))return;
    for(Object item:rows)if(item instanceof PortfolioRebalancingCosts.Row row){
      String kind=row.label(),actualScope=scope;
      if("CONCENTRATION_REDISTRIBUTION".equals(scope)){
        String suffix=" · fixed-capital redistribution",noSale=" · no-sale contribution";
        if(kind.endsWith(suffix))kind=kind.substring(0,kind.length()-suffix.length());
        else if(kind.endsWith(noSale)){
          kind=kind.substring(0,kind.length()-noSale.length());actualScope="CONCENTRATION_CONTRIBUTION";
        }else continue;
      }
      Key key=new Key(actualScope,kind);
      out.add(compare(actualScope,kind,row,sales.get(key),loads.get(key)));
    }
  }

  static Comparison compare(String scope,String kind,PortfolioRebalancingCosts.Row row,
      PortfolioSaleResearch.Scenario sale,PortfolioFundExitLoad.Scenario load){
    List<String> gaps=new ArrayList<>();
    BigDecimal exit=null,unused=null,used=null;
    boolean noSale=row.saleNotional().signum()==0;
    if(noSale){
      // A zero rounded turnover is not proof of no sale unless the corresponding
      // scenario also agrees, except for the explicitly purchase-only contribution.
      if("CONCENTRATION_CONTRIBUTION".equals(scope)||
          (sale!=null&&"NO_HYPOTHETICAL_SALE".equals(sale.status()))){
        exit=ZERO;unused=ZERO;used=ZERO;
      }else gaps.add("No-sale evidence not reconciled.");
    }else if(sale==null||!"PROVISIONAL_SALE_EVIDENCE".equals(sale.status())||
        sale.grossProceeds()==null||sale.sales().isEmpty()){
      gaps.add("Reconciled hypothetical sale evidence required.");
    }else if(sale.grossProceeds().subtract(row.saleNotional()).abs()
        .compareTo(new BigDecimal("0.01").multiply(BigDecimal.valueOf(sale.sales().size()+1L)))>0){
      gaps.add("Sale proceeds do not reconcile with the turnover estimate.");
    }else{
      boolean fundSale=sale.sales().stream().anyMatch(s->"MUTUAL_FUND".equals(s.assetType()));
      boolean equityOnly=sale.sales().stream().allMatch(s->"EQUITY".equals(s.assetType()));
      if(equityOnly)exit=ZERO;
      else if(fundSale&&load!=null&&"CONDITIONAL_CURRENT_TERMS".equals(load.status())&&
          load.hypotheticalFundExitLoad()!=null&&load.hypotheticalFundExitLoad().signum()>=0&&
          load.hypotheticalFundExitLoad().compareTo(sale.grossProceeds())<=0)exit=load.hypotheticalFundExitLoad();
      else gaps.add("Complete conditional fund exit-load evidence required.");
      var tax=sale.taxReference();
      if(equityOnly&&tax!=null&&"CONDITIONAL_REFERENCE_ONLY".equals(tax.status())&&
          tax.baseTaxIfFullThresholdUnused()!=null&&tax.baseTaxIfThresholdAlreadyUsed()!=null){
        unused=tax.baseTaxIfFullThresholdUnused();used=tax.baseTaxIfThresholdAlreadyUsed();
      }else if(fundSale)gaps.add("Fund tax classification and applicable acquisition-specific treatment are not verified.");
      else gaps.add("Conditional equity tax reference unavailable.");
    }
    List<Estimate> estimates=new ArrayList<>();
    for(var e:row.estimates()){
      BigDecimal withExit=exit==null?null:e.additionalCashIncludingCost().add(exit);
      estimates.add(new Estimate(e.basisPointsPerSide(),e.hypotheticalCost(),e.additionalCashIncludingCost(),
        withExit,withExit==null||unused==null?null:withExit.add(unused),withExit==null||used==null?null:withExit.add(used)));
    }
    return new Comparison(scope,kind,gaps.isEmpty()?"CONDITIONAL_COMPONENTS_AVAILABLE":"PARTIAL_COMPONENTS",
      row.purchaseNotional(),row.saleNotional(),row.additionalCashBeforeCost(),exit,unused,used,estimates,List.copyOf(gaps));
  }
}
