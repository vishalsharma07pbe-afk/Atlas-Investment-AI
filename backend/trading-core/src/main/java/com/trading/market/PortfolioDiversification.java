package com.trading.market;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.*;
import java.util.*;

/** Owner-local exposure analysis from recorded values and cached public metadata. */
final class PortfolioDiversification {
 private PortfolioDiversification(){}
 private static final BigDecimal ZERO=BigDecimal.ZERO;
 private static final BigDecimal HUNDRED=BigDecimal.valueOf(100);
 private static final String UNKNOWN="Unknown";
 private record Position(String label,BigDecimal value){}
 static Map<String,Object> summarize(List<Map<String,Object>> holdings,ObjectMapper json){
  BigDecimal total=ZERO,knownEquity=ZERO,directEquity=ZERO,fundValue=ZERO,knownFund=ZERO;
  int unpriced=0,unresolved=0;
  Map<String,Position> identities=new TreeMap<>();
  Map<String,BigDecimal> sectors=new TreeMap<>(),categories=new TreeMap<>(),assets=new TreeMap<>();
  // Conflicting sector labels for the same ISIN are unknown, not two exposures.
  Map<String,Set<String>> identitySectors=new HashMap<>();
  for(var holding:holdings){
   JsonNode h=json.valueToTree(holding);
   if(!"EQUITY".equals(h.path("asset_type").asText()))continue;
   String isin=h.path("isin").asText();
   JsonNode company=h.path("thesis_evidence").path("company_evidence");
   String sector=label(company.path("sections").path("profile").path("data").path("sector"));
   if(isin.matches("IN[A-Z0-9]{10}")&&isin.equals(company.path("isin").asText())&&!UNKNOWN.equals(sector))
     identitySectors.computeIfAbsent(isin,k->new TreeSet<>()).add(sector);
  }
  for(var holding:holdings){
   JsonNode h=json.valueToTree(holding);
   BigDecimal value=amount(h.path("recorded_market_value"));
   if(value==null){unpriced++;continue;}
   if(value.signum()==0)continue;
   total=total.add(value);
   String type=h.path("asset_type").asText(),symbol=h.path("symbol").asText();
   String asset=Set.of("EQUITY","MUTUAL_FUND").contains(type)?type:"OTHER";
   assets.merge(asset,value,BigDecimal::add);
   String identity=null;
   if("EQUITY".equals(type)){
    directEquity=directEquity.add(value);
    String isin=h.path("isin").asText();
    String sector=UNKNOWN;
    if(isin.matches("IN[A-Z0-9]{10}")){
     identity="ISIN:"+isin;
     Set<String> labels=identitySectors.getOrDefault(isin,Set.of());
     if(labels.size()==1)sector=labels.iterator().next();
    }
    if(!UNKNOWN.equals(sector))knownEquity=knownEquity.add(value);
    sectors.merge(sector,value,BigDecimal::add);
   }else if("MUTUAL_FUND".equals(type)){
    fundValue=fundValue.add(value);
    String category=UNKNOWN;
    if(symbol.matches("[0-9]{1,18}")&&symbol.equals(h.path("exact_scheme_code").asText())){
     identity="AMFI:"+symbol;
     category=label(h.path("scheme_category"));
    }
    if(!UNKNOWN.equals(category))knownFund=knownFund.add(value);
    categories.merge(category,value,BigDecimal::add);
   }
   if(identity==null){unresolved++;continue;}
   Position old=identities.get(identity);
   identities.put(identity,new Position(old==null?symbol:old.label(),old==null?value:old.value().add(value)));
  }
  var ranked=identities.values().stream().sorted(Comparator.comparing(Position::value).reversed().thenComparing(Position::label)).toList();
  List<String> prompts=new ArrayList<>();
  List<Map<String,Object>> concentration=new ArrayList<>();
  BigDecimal topThree=ranked.stream().limit(3).map(Position::value).reduce(ZERO,BigDecimal::add);
  for(Position p:ranked)if(over(p.value(),total,25))prompts.add(p.label()+" exceeds 25% of recorded priced portfolio value after exact identity aggregation.");
  if(over(topThree,total,60))prompts.add("Top three resolved investment identities exceed 60% of recorded priced portfolio value.");
  for(var e:sectors.entrySet())if(!UNKNOWN.equals(e.getKey())&&over(e.getValue(),directEquity,40))
    prompts.add(e.getKey()+" exceeds 40% of recorded direct-equity value. Review sector exposure.");
  // Structured observations use the same unrounded thresholds as the existing prompts.
  for(Position p:ranked)if(over(p.value(),total,25))
    concentration.add(Map.of("kind","SINGLE_IDENTITY","label",p.label(),"weight_percent",pct(p.value(),total),"threshold_percent",25));
  if(over(topThree,total,60))concentration.add(Map.of("kind","TOP_THREE","label","Top three resolved identities","weight_percent",pct(topThree,total),"threshold_percent",60));
  for(var e:sectors.entrySet())if(!UNKNOWN.equals(e.getKey())&&over(e.getValue(),directEquity,40))
    concentration.add(Map.of("kind","DIRECT_EQUITY_SECTOR","label",e.getKey(),"weight_percent",pct(e.getValue(),directEquity),"threshold_percent",40));
  if(unpriced>0||unresolved>0||knownEquity.compareTo(directEquity)<0||knownFund.compareTo(fundValue)<0)
    prompts.add("Complete missing recorded valuations, exact identities and classification evidence before relying on diversification measures.");
  Map<String,Object> out=new LinkedHashMap<>();
  out.put("status",total.signum()==0?"NO_PRICED_VALUE":unpriced>0||unresolved>0||knownEquity.compareTo(directEquity)<0||knownFund.compareTo(fundValue)<0?"PARTIAL_COVERAGE":"CLASSIFIED_PRICED_HOLDINGS");
  out.put("priced_value",total);out.put("unpriced_count",unpriced);out.put("unresolved_identity_count",unresolved);
  out.put("resolved_identity_count",ranked.size());out.put("top_three_resolved_weight_percent",pct(topThree,total));
  out.put("asset_exposure",exposure(assets,total));out.put("direct_equity_sector_exposure",exposure(sectors,directEquity));
  out.put("fund_category_exposure",exposure(categories,fundValue));
  out.put("sector_coverage_percent",pct(knownEquity,directEquity));out.put("fund_category_coverage_percent",pct(knownFund,fundValue));
  out.put("review_prompts",prompts);
  out.put("concentration_observations",concentration);
  boolean recent=holdings.stream().allMatch(h->Boolean.TRUE.equals(h.get("recorded_valuation_recent")));
  out.put("allocation_research",PortfolioAllocationResearch.assess(ranked.stream().map(Position::value).toList(),
    total,recent&&unpriced==0&&unresolved==0));
  out.put("exposure_stress",PortfolioExposureStress.assess(total,assets,identities.entrySet().stream()
    .map(e->new PortfolioExposureStress.Exposure(e.getKey(),e.getValue().label(),e.getValue().value())).toList(),
    sectors,recent&&unpriced==0,unresolved==0,knownEquity.compareTo(directEquity)==0));
  out.put("notice","Recorded priced holdings only, not independently verified live valuations. Sector weights use direct equity value; fund category weights use fund value. Exact identities aggregate duplicate holdings. Fund underlying exposures, overlap, correlations and optimal allocations are not established. Thresholds are illustrative review triggers, not personalized targets.");
  return out;
 }
 private static BigDecimal amount(JsonNode n){
  if(!n.isNumber()||!Double.isFinite(n.asDouble()))return null;
  BigDecimal value=n.decimalValue();
  return value.signum()<0?null:value;
 }
 private static String label(JsonNode n){
  if(!n.isTextual())return UNKNOWN;
  String s=n.asText().trim().replaceAll("\\s+"," ").toLowerCase(Locale.ROOT);
  return s.isBlank()||Set.of("unknown","n/a","na","not available","-").contains(s)?UNKNOWN:s;
 }
 private static BigDecimal pct(BigDecimal value,BigDecimal total){
  return total.signum()==0?null:value.multiply(HUNDRED).divide(total,2,RoundingMode.HALF_UP);
 }
 private static boolean over(BigDecimal value,BigDecimal total,int limit){
  return total.signum()>0&&value.multiply(HUNDRED).compareTo(total.multiply(BigDecimal.valueOf(limit)))>0;
 }
 private static List<Map<String,Object>> exposure(Map<String,BigDecimal> groups,BigDecimal total){
  return groups.entrySet().stream().sorted(Map.Entry.<String,BigDecimal>comparingByValue().reversed().thenComparing(Map.Entry.comparingByKey()))
    .map(e->Map.<String,Object>of("label",e.getKey(),"weight_percent",pct(e.getValue(),total))).toList();
 }
}
