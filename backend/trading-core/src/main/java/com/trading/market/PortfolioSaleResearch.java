package com.trading.market;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.*;
import java.time.LocalDate;
import java.util.*;

/** Hypothetical sale proceeds and provisional journal FIFO gains, never tax liability. */
final class PortfolioSaleResearch {
  private PortfolioSaleResearch(){}
  private static final MathContext MC=MathContext.DECIMAL128;
  private static final BigDecimal ZERO=BigDecimal.ZERO;
  private record Position(String identity,String symbol,String asset,String exchange,BigDecimal quantity,
      BigDecimal price,BigDecimal value,PortfolioJournalLots.Holding journal){}
  record Sale(String identity,String symbol,String assetType,BigDecimal hypotheticalQuantity,
      BigDecimal grossProceeds,BigDecimal provisionalOpenCost,BigDecimal grossGainOrLoss,
      long youngestCalendarDays,long oldestCalendarDays){}
  record Scenario(String scope,String kind,String status,BigDecimal grossProceeds,BigDecimal provisionalOpenCost,
      BigDecimal grossGainOrLoss,List<Sale> sales,List<String> withheld,PortfolioEquityTaxReference.Reference taxReference){}
  private static BigDecimal number(JsonNode node){
    return node.isNumber()&&Double.isFinite(node.asDouble())?node.decimalValue():null;
  }
  private static BigDecimal amount(Map<String,Object> row,String key){
    return row.get(key) instanceof BigDecimal n&&Double.isFinite(n.doubleValue())?n:null;
  }
  private static String key(String asset,String symbol){return asset+":"+symbol.toUpperCase(Locale.ROOT);}
  private static BigDecimal money(BigDecimal n){return n.setScale(2,RoundingMode.HALF_UP);}
  private static String identity(Map<String,Object> row){
    if("EQUITY".equals(row.get("asset_type"))&&row.get("isin") instanceof String isin&&isin.matches("INE[A-Z0-9]{9}"))return isin;
    if("MUTUAL_FUND".equals(row.get("asset_type"))&&row.get("exact_scheme_code") instanceof Number code&&
        String.valueOf(code.longValue()).matches("[1-9][0-9]{5,8}")&&String.valueOf(code.longValue()).equals(row.get("symbol")))
      return "AMFI:"+code.longValue();
    return null;
  }
  static Map<String,Object> assess(List<Map<String,Object>> holdings,Map<String,Object> report,ObjectMapper json,LocalDate today){
    var out=new LinkedHashMap<String,Object>();
    out.put("notice","Hypothetical gross sale gain or loss at recent recorded prices using provisional FIFO journal lots only. Fractional units are mathematical approximations, not executable quantities. Matching symbol-level journal cost and quantity does not verify demat or folio tax lots. Separate conditional listed-equity tax reference arithmetic is not a determination of eligibility or tax liability. No loss offset, charges, exit load, grandfathering or corporate-action adjustment is assumed. Unsupported sale evidence withholds the entire scenario's gain totals.");
    Map<String,PortfolioJournalLots.Holding> journals=new HashMap<>();
    if(report.get("journal_lot_reconciliation") instanceof Map<?,?> journal&&journal.get("holdings") instanceof List<?> lots)
      for(Object item:lots)if(item instanceof PortfolioJournalLots.Holding h)journals.put(key(h.assetType(),h.symbol()),h);
    List<Scenario> scenarios=new ArrayList<>();
    var diversification=json.valueToTree(report.get("diversification"));
    JsonNode allocation=diversification.path("allocation_research");
    if("HYPOTHETICAL_SCENARIOS_AVAILABLE".equals(allocation.path("status").asText())){
      for(JsonNode s:allocation.path("scenarios")){
        String kind=s.path("hypotheticalNewIdentities").asInt()+" new identities";
        BigDecimal total=number(allocation.path("recorded_value")),redistributed=number(s.path("hypotheticalRedistributedCapital"));
        scenarios.add(proportional(holdings,journals,kind,total,redistributed,today));
      }
    }
    JsonNode correlation=json.valueToTree(report.get("equity_correlation"));
    historical(holdings,journals,correlation.path("historical_allocation"),false,scenarios,today);
    historical(holdings,journals,correlation.path("cross_asset_allocation"),true,scenarios,today);
    out.put("status",scenarios.isEmpty()?"NO_ELIGIBLE_ALLOCATION_SCENARIOS":
      scenarios.stream().anyMatch(s->"PROVISIONAL_SALE_EVIDENCE".equals(s.status())||"NO_HYPOTHETICAL_SALE".equals(s.status()))?
        "SCENARIO_RESEARCH_AVAILABLE":"INSUFFICIENT_SALE_EVIDENCE");
    out.put("scenarios",scenarios);
    return out;
  }
  private static Map<String,Position> positions(List<Map<String,Object>> holdings,Map<String,PortfolioJournalLots.Holding> journals,
      boolean equityOnly,List<String> blockers){
    Map<String,Position> positions=new TreeMap<>();
    for(var h:holdings){
      String asset=String.valueOf(h.get("asset_type")),symbol=String.valueOf(h.get("symbol"));
      if(equityOnly&&!"EQUITY".equals(asset))continue;
      BigDecimal v=amount(h,"market_value"),q=amount(h,"quantity"),p=amount(h,"last_price");
      if(v==null||v.signum()<0||!Boolean.TRUE.equals(h.get("recorded_valuation_recent"))){
        blockers.add(symbol+": recent recorded value required");continue;
      }
      if(v.signum()==0)continue;
      String id=identity(h);
      if(id==null||q==null||q.signum()<=0||p==null||p.signum()<=0||q.multiply(p).compareTo(v)!=0){
        blockers.add(symbol+": exact identity or consistent recorded quantity and price required");continue;
      }
      if(positions.putIfAbsent(id,new Position(id,symbol,asset,String.valueOf(h.get("exchange")),q,p,v,journals.get(key(asset,symbol))))!=null)
        blockers.add(symbol+": duplicate exact identity; journal allocation ambiguous");
    }
    return positions;
  }
  private static Scenario proportional(List<Map<String,Object>> holdings,Map<String,PortfolioJournalLots.Holding> journals,
      String kind,BigDecimal total,BigDecimal redistributed,LocalDate today){
    List<String> blockers=new ArrayList<>();
    var positions=positions(holdings,journals,false,blockers);
    if(!validTotal(positions,total)||redistributed==null||redistributed.signum()<0||redistributed.compareTo(total)>0)
      blockers.add("Scenario amount does not reconcile with recorded portfolio");
    if(!blockers.isEmpty())return withheld("CONCENTRATION_REDISTRIBUTION",kind,blockers);
    Map<String,BigDecimal> targets=new TreeMap<>();
    for(Position p:positions.values())targets.put(p.identity(),p.value().multiply(redistributed).divide(total,MC));
    return evaluate("CONCENTRATION_REDISTRIBUTION",kind,positions,targets,today);
  }
  private static void historical(List<Map<String,Object>> holdings,Map<String,PortfolioJournalLots.Holding> journals,
      JsonNode report,boolean mixed,List<Scenario> out,LocalDate today){
    if(!"HISTORICAL_COMPARISON_AVAILABLE".equals(report.path("status").asText()))return;
    String scope=mixed?"MIXED_ALLOCATION":"DIRECT_EQUITY_ALLOCATION";
    List<String> blockers=new ArrayList<>();
    var positions=positions(holdings,journals,!mixed,blockers);
    BigDecimal total=number(report.path(mixed?"recorded_value":"direct_equity_value"));
    if(!validTotal(positions,total))blockers.add("Scenario value does not reconcile with recorded holdings");
    for(JsonNode alternative:report.path("alternatives")){
      String kind=alternative.path("kind").asText();
      if(!Set.of("CURRENT_WEIGHTS","HALFWAY_TO_EQUAL","EQUAL_WEIGHTS").contains(kind))continue;
      if(!blockers.isEmpty()){out.add(withheld(scope,kind,blockers));continue;}
      Map<String,BigDecimal> targets=new TreeMap<>();
      Set<String> seen=new HashSet<>();
      boolean valid=true;
      BigDecimal weights=ZERO;
      for(JsonNode w:alternative.path("weights")){
        String id=w.path(mixed?"identity":"isin").asText();
        BigDecimal weight=number(w.path("weightPercent"));
        Position p=positions.get(id);
        if(p==null||!seen.add(id)||weight==null||weight.signum()<0||weight.compareTo(BigDecimal.valueOf(100))>0){valid=false;break;}
        weights=weights.add(weight);
        BigDecimal sale=p.value().subtract(total.multiply(weight).movePointLeft(2)).max(ZERO);
        // The current-weight alternative is the unchanged baseline; avoid floating point residue.
        targets.put(id,"CURRENT_WEIGHTS".equals(kind)?ZERO:sale);
      }
      if(!valid||seen.size()!=positions.size()||weights.subtract(BigDecimal.valueOf(100)).abs().compareTo(new BigDecimal("0.000001"))>0){
        out.add(withheld(scope,kind,List.of("Scenario weights do not reconcile with exact recorded identities")));continue;
      }
      out.add(evaluate(scope,kind,positions,targets,today));
    }
  }
  private static boolean validTotal(Map<String,Position> positions,BigDecimal total){
    return total!=null&&total.signum()>0&&positions.values().stream().map(Position::value).reduce(ZERO,BigDecimal::add).compareTo(total)==0;
  }
  private static Scenario evaluate(String scope,String kind,Map<String,Position> positions,Map<String,BigDecimal> targets,LocalDate today){
    List<String> blockers=new ArrayList<>();List<Sale> sales=new ArrayList<>();
    List<PortfolioEquityTaxReference.ConsumedLot> taxLots=new ArrayList<>();
    for(var target:targets.entrySet()){
      Position p=positions.get(target.getKey());
      BigDecimal gross=money(target.getValue()).min(p.value());
      if(gross.signum()==0)continue;
      PortfolioJournalLots.Holding h=p.journal();
      if(h==null||!"PROVISIONAL_JOURNAL_RECONCILED".equals(h.status())||h.openLots().isEmpty()||
          h.recordedQuantity()==null||h.recordedQuantity().compareTo(p.quantity())!=0){
        blockers.add(p.symbol()+": reconciled journal acquisition lots required");continue;
      }
      BigDecimal quantity=gross.divide(p.price(),MC).min(p.quantity());
      BigDecimal left=quantity,cost=ZERO;
      long youngest=Long.MAX_VALUE,oldest=0;
      for(var lot:h.openLots()){
        if(left.signum()==0)break;
        BigDecimal consumed=left.min(lot.quantity());
        cost=cost.add(consumed.multiply(lot.unitPrice(),MC));
        taxLots.add(new PortfolioEquityTaxReference.ConsumedLot(p.asset(),p.exchange(),LocalDate.parse(lot.acquired()),consumed.multiply(p.price().subtract(lot.unitPrice()),MC)));
        left=left.subtract(consumed);
        youngest=Math.min(youngest,lot.calendarDaysHeld());oldest=Math.max(oldest,lot.calendarDaysHeld());
      }
      if(left.signum()!=0){blockers.add(p.symbol()+": insufficient reconstructed open units");continue;}
      BigDecimal proceeds=money(gross),basis=money(cost);
      sales.add(new Sale(p.identity(),p.symbol(),p.asset(),quantity,proceeds,basis,proceeds.subtract(basis),youngest,oldest));
    }
    if(!blockers.isEmpty())return withheld(scope,kind,blockers);
    BigDecimal proceeds=sales.stream().map(Sale::grossProceeds).reduce(ZERO,BigDecimal::add);
    BigDecimal cost=sales.stream().map(Sale::provisionalOpenCost).reduce(ZERO,BigDecimal::add);
    return new Scenario(scope,kind,sales.isEmpty()?"NO_HYPOTHETICAL_SALE":"PROVISIONAL_SALE_EVIDENCE",proceeds,cost,proceeds.subtract(cost),sales,List.of(),PortfolioEquityTaxReference.assess(taxLots,today));
  }
  private static Scenario withheld(String scope,String kind,List<String> blockers){
    return new Scenario(scope,kind,"INSUFFICIENT_SALE_EVIDENCE",null,null,null,List.of(),List.copyOf(blockers),PortfolioEquityTaxReference.withheld("INSUFFICIENT_SALE_EVIDENCE",List.copyOf(blockers)));
  }
}
