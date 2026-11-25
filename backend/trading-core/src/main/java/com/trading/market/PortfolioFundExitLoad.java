package com.trading.market;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.*;
import java.time.*;
import java.util.*;
import java.util.regex.Pattern;

/** Conditional current-disclosure illustration, never a verified redemption charge. */
final class PortfolioFundExitLoad {
  private PortfolioFundExitLoad(){}
  private static final MathContext MC=MathContext.DECIMAL128;
  private static final BigDecimal ZERO=BigDecimal.ZERO;
  private static final Pattern SIMPLE=Pattern.compile(
    "^([0-9]{1,2}(?:\\.[0-9]{1,4})?)% if redeemed on or before ([1-9][0-9]{0,3}) days from (?:the )?date of allotment[.;] (?:nil|no exit load) thereafter\\.?$");
  record Rule(BigDecimal ratePercent,int inclusiveDays){}
  record Fund(String schemeCode,String status,String disclosureDate,String disclosureText,
      BigDecimal hypotheticalLoad,BigDecimal proceedsAfterLoad,String reason){}
  record Scenario(String scope,String kind,String status,BigDecimal hypotheticalFundExitLoad,List<Fund> funds){}
  static Rule parse(String text){
    String normalized=text.strip().replaceAll("\\s+"," ").toLowerCase(Locale.ROOT);
    if(Set.of("nil","nil.","no exit load","no exit load.").contains(normalized))return new Rule(ZERO,0);
    var match=SIMPLE.matcher(normalized);
    if(!match.matches())return null;
    BigDecimal rate=new BigDecimal(match.group(1));
    return rate.compareTo(BigDecimal.TEN)<=0?new Rule(rate,Integer.parseInt(match.group(2))):null;
  }
  static Map<String,Object> assess(Map<String,Object> review,ObjectMapper json,Instant now){
    var out=new LinkedHashMap<String,Object>();
    out.put("notice","Conditional illustration applying current dated secondary disclosure text to recorded acquisition dates as assumed allotment dates. Historical terms at allotment, amendments, free-unit allowances, switches, actual NAV, folio and official AMC verification are not established. Only complete explicit nil or simple inclusive day-based single-rate terms are calculated. Missing or complex terms are withheld, never zero. Excludes tax and other costs.");
    Map<String,PortfolioJournalLots.Holding> journals=new HashMap<>();
    if(review.get("journal_lot_reconciliation") instanceof Map<?,?> journal&&journal.get("holdings") instanceof List<?> lots)
      for(Object item:lots)if(item instanceof PortfolioJournalLots.Holding h&&"MUTUAL_FUND".equals(h.assetType()))journals.put(h.symbol(),h);
    Map<String,JsonNode> evidence=new HashMap<>();
    JsonNode holdings=json.valueToTree(review.get("holdings"));
    for(JsonNode h:holdings)if("MUTUAL_FUND".equals(h.path("asset_type").asText())){
      String code=h.path("symbol").asText();
      if(code.matches("[1-9][0-9]{5,8}")&&code.equals(h.path("exact_scheme_code").asText()))
        evidence.merge(code,h,(a,b)->json.createObjectNode());
    }
    List<Scenario> scenarios=new ArrayList<>();
    if(review.get("sale_research") instanceof Map<?,?> sale&&sale.get("scenarios") instanceof List<?> raw)
      for(Object item:raw)if(item instanceof PortfolioSaleResearch.Scenario s){
        if(!"PROVISIONAL_SALE_EVIDENCE".equals(s.status()))continue;
        List<Fund> funds=new ArrayList<>();
        for(var position:s.sales())if("MUTUAL_FUND".equals(position.assetType()))
          funds.add(estimate(position,journals.get(position.symbol()),evidence.get(position.symbol()),now));
        if(funds.isEmpty())continue;
        boolean complete=funds.stream().allMatch(f->"CONDITIONAL_CURRENT_TERMS".equals(f.status()));
        scenarios.add(new Scenario(s.scope(),s.kind(),complete?"CONDITIONAL_CURRENT_TERMS":"INCOMPLETE_EXIT_LOAD_EVIDENCE",
          complete?funds.stream().map(Fund::hypotheticalLoad).reduce(ZERO,BigDecimal::add):null,funds));
      }
    out.put("status",scenarios.isEmpty()?"NO_SUPPORTED_FUND_SALE_SCENARIOS":"FUND_EXIT_LOAD_RESEARCH");
    out.put("scenarios",scenarios);
    return out;
  }
  static Fund estimate(PortfolioSaleResearch.Sale sale,PortfolioJournalLots.Holding journal,JsonNode holding,Instant now){
    String code=sale.symbol();
    if(holding==null||!code.matches("[1-9][0-9]{5,8}")||!("AMFI:"+code).equals(sale.identity()))
      return withheld(code,null,null,"Exact matched scheme disclosure required.");
    var e=holding.path("fund_thesis_evidence");var d=e.path("disclosure");
    if(!"SECONDARY_REPORTED_EVIDENCE".equals(e.path("status").asText())||
        !"TIGZIG_AMFI_DERIVED".equals(d.path("source").asText())||
        !"SECONDARY_REPORTED_NOT_INDEPENDENTLY_VERIFIED".equals(d.path("status").asText())||
        !code.equals(d.path("scheme_code").asText())||!d.path("isin").asText().matches("IN[A-Z0-9]{10}")||
        !Set.of("DIRECT","REGULAR").contains(d.path("plan").asText()))
      return withheld(code,null,null,"Exact current secondary disclosure required.");
    LocalDate today=now.atZone(MarketCalendarService.IST).toLocalDate(),document;
    try{
      Instant collected=OffsetDateTime.parse(d.path("collected_at").asText()).toInstant();
      document=LocalDate.parse(d.path("document_date").asText());
      if(collected.isAfter(now)||collected.isBefore(now.minus(Duration.ofDays(3)))||
          document.isAfter(collected.atZone(MarketCalendarService.IST).toLocalDate())||
          document.isBefore(today.minusDays(365)))
        return withheld(code,null,null,"Disclosure collection or document date is stale or invalid.");
    }catch(RuntimeException ex){return withheld(code,null,null,"Dated disclosure required.");}
    String text=d.path("exit_load").isTextual()?d.path("exit_load").asText():null;
    if(text==null||text.isBlank()||text.length()>2000)return withheld(code,document.toString(),null,"No usable exit-load disclosure.");
    for(JsonNode conflict:d.path("conflicts"))if(conflict.asText().contains("EXIT_LOAD"))
      return withheld(code,document.toString(),text,"Conflicting exit-load disclosure.");
    Rule rule=parse(text);
    if(rule==null)return withheld(code,document.toString(),text,"Complex or incomplete terms require official scheme review.");
    if(journal==null||!"PROVISIONAL_JOURNAL_RECONCILED".equals(journal.status())||journal.openLots().isEmpty()||
        sale.hypotheticalQuantity()==null||sale.hypotheticalQuantity().signum()<=0||
        sale.grossProceeds()==null||sale.grossProceeds().signum()<0)
      return withheld(code,document.toString(),text,"Provisional FIFO sale units required.");
    BigDecimal remaining=sale.hypotheticalQuantity(),chargeable=ZERO;
    for(var lot:journal.openLots()){
      if(remaining.signum()==0)break;
      BigDecimal used=remaining.min(lot.quantity());
      long age;
      try{age=java.time.temporal.ChronoUnit.DAYS.between(LocalDate.parse(lot.acquired()),today);}
      catch(RuntimeException ex){return withheld(code,document.toString(),text,"Invalid acquisition date.");}
      if(age<0)return withheld(code,document.toString(),text,"Future acquisition date.");
      if(age<=rule.inclusiveDays())chargeable=chargeable.add(used);
      remaining=remaining.subtract(used);
    }
    if(remaining.signum()!=0)return withheld(code,document.toString(),text,"Insufficient recorded open units.");
    BigDecimal load=sale.grossProceeds().multiply(chargeable,MC).divide(sale.hypotheticalQuantity(),MC)
      .multiply(rule.ratePercent()).movePointLeft(2).setScale(2,RoundingMode.HALF_UP);
    return new Fund(code,"CONDITIONAL_CURRENT_TERMS",document.toString(),text,load,sale.grossProceeds().subtract(load),null);
  }
  private static Fund withheld(String code,String date,String text,String reason){
    return new Fund(code,"EXIT_LOAD_WITHHELD",date,text,null,null,reason);
  }
}
