package com.trading.market;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.*;
import java.time.*;
import java.util.*;

/** Local estimates using current recorded values and dated secondary fund weights. */
final class PortfolioLookThrough {
  private PortfolioLookThrough(){}
  private static final BigDecimal ZERO=BigDecimal.ZERO,HUNDRED=BigDecimal.valueOf(100),TOLERANCE=new BigDecimal("0.0001");
  private record Composition(String code,String fundId,LocalDate date,Map<String,BigDecimal> weights,BigDecimal coverage){}
  private record Fund(Composition composition,BigDecimal value){}
  private record Sector(String sector,BigDecimal directValue,BigDecimal indirectValue,BigDecimal estimatedValue,BigDecimal portfolioPercent,boolean reviewConcentration){}
  private record Exposure(String isin,BigDecimal directValue,BigDecimal indirectValue,BigDecimal estimatedValue,BigDecimal portfolioPercent,int contributingSchemes){}
  private record Pair(String schemeA,String schemeB,boolean sameUnderlyingFund,int commonEquities,BigDecimal sharedWeightPercent,BigDecimal coverageA,BigDecimal coverageB){}
  private static BigDecimal number(JsonNode n){
    return n.isNumber()&&Double.isFinite(n.asDouble())?n.decimalValue().stripTrailingZeros():null;
  }
  private static boolean recent(JsonNode n,Instant now){
    try{Instant at=OffsetDateTime.parse(n.asText()).toInstant();return !at.isAfter(now)&&!at.isBefore(now.minus(Duration.ofDays(3)));}
    catch(RuntimeException ex){return false;}
  }
  private static boolean equityIsin(String value){return value.matches("INE[A-Z0-9]{9}");}
  private static Composition composition(JsonNode h,Instant now,LocalDate today){
    String code=h.path("exact_scheme_code").asText();
    if(!code.matches("[1-9][0-9]{5,8}")||!code.equals(h.path("symbol").asText()))return null;
    var evidence=h.path("fund_thesis_evidence");var d=evidence.path("disclosure");var p=evidence.path("portfolio");
    String fundId=d.path("fund_id").asText();
    if(!"SECONDARY_REPORTED_EVIDENCE".equals(evidence.path("status").asText())||
        !"TIGZIG_AMFI_DERIVED".equals(d.path("source").asText())||
        !"TIGZIG_AMC_DERIVED".equals(p.path("source").asText())||
        !"SECONDARY_COMPOSITION_ONLY".equals(p.path("status").asText())||
        !code.equals(d.path("scheme_code").asText())||!code.equals(p.path("scheme_code").asText())||
        fundId.isBlank()||fundId.length()>80||!fundId.equals(p.path("fund_id").asText())||
        !d.path("isin").asText().matches("IN[A-Z0-9]{10}")||
        !Set.of("DIRECT","REGULAR").contains(d.path("plan").asText())||
        !recent(d.path("collected_at"),now)||!recent(p.path("collected_at"),now))return null;
    LocalDate day;
    try{day=LocalDate.parse(p.path("portfolio_date").asText());}catch(RuntimeException ex){return null;}
    if(day.isAfter(today)||day.isBefore(today.minusDays(60)))return null;
    var weights=p.path("exact_equity_weights");
    BigDecimal reported=number(p.path("exact_listed_equity_weight_percent")),total=number(p.path("reported_weight_total_percent"));
    if(!weights.isObject()||weights.size()>500||weights.size()!=p.path("exact_equity_count").asInt(-1)||
        reported==null||total==null||total.compareTo(new BigDecimal("99.5"))<0||total.compareTo(new BigDecimal("100.5"))>0)return null;
    Map<String,BigDecimal> valid=new TreeMap<>();
    var fields=weights.fields();
    while(fields.hasNext()){
      var field=fields.next();BigDecimal value=number(field.getValue());
      if(!equityIsin(field.getKey())||value==null||value.signum()<=0||value.compareTo(HUNDRED)>0)return null;
      valid.put(field.getKey(),value);
    }
    BigDecimal coverage=valid.values().stream().reduce(ZERO,BigDecimal::add);
    if(coverage.compareTo(HUNDRED)>0||reported.subtract(coverage).abs().compareTo(TOLERANCE)>0)return null;
    return new Composition(code,fundId,day,valid,coverage);
  }
  private static void sectorEvidence(Map<String,Set<String>> labels,String isin,JsonNode evidence,Instant now){
    if(!equityIsin(isin)||!"UPSTOX".equals(evidence.path("provider").asText()))return;
    try{
      Instant stamp=OffsetDateTime.parse(evidence.path("retrieved_at").asText()).toInstant();
      if(stamp.isAfter(now)||stamp.isBefore(now.minus(Duration.ofHours(24))))return;
    }catch(RuntimeException ex){return;}
    JsonNode field=evidence.path("sector");
    if(!field.isTextual())return;
    String label=field.asText().trim().replaceAll("\\s+"," ").toLowerCase(Locale.ROOT);
    if(label.isBlank()||label.length()>180||Set.of("unknown","n/a","na","not available","-","null").contains(label))return;
    labels.computeIfAbsent(isin,k->new TreeSet<>()).add(label);
  }
  private static BigDecimal pct(BigDecimal value,BigDecimal total){return value.multiply(HUNDRED).divide(total,2,RoundingMode.HALF_UP);}
  private static BigDecimal money(BigDecimal v){return v.setScale(2,RoundingMode.HALF_UP);}

  static Map<String,Object> assess(List<Map<String,Object>> holdings,ObjectMapper json,Instant now){
    var out=new LinkedHashMap<String,Object>();
    out.put("notice","Estimates combine recent recorded direct values and original reported fund NAV weights from the newest available common disclosure-date cohort. No normalization. Excludes missing, older-date, foreign, unmapped and indirect fund-unit exposures; unmodeled capital is not assumed risk-free. Same-date fund overlap sums minimum shared listed-equity weights with at least 80% exact coverage per scheme. Secondary disclosures may be outdated or inaccurate. Not a live exposure or a recommendation.");
    out.put("exposures",List.of());out.put("overlap_pairs",List.of());
    out.put("risk_observations",List.of());out.put("risk_observation_count",0);
    BigDecimal total=ZERO,fundValue=ZERO,directValue=ZERO;
    Map<String,BigDecimal> direct=new TreeMap<>();
    Map<String,Set<String>> sectorLabels=new HashMap<>();
    Map<String,List<JsonNode>> fundSectorEvidence=new HashMap<>();
    Map<String,Fund> funds=new TreeMap<>();
    Set<String> conflicts=new HashSet<>();
    int positiveFunds=0;
    LocalDate today=now.atZone(MarketCalendarService.IST).toLocalDate();
    for(var holding:holdings){
      JsonNode h=json.valueToTree(holding);
      BigDecimal value=number(h.path("recorded_market_value"));
      if(value==null||value.signum()<0||!h.path("recorded_valuation_recent").asBoolean(false)){
        out.put("status","INSUFFICIENT_RECENT_VALUATIONS");return out;
      }
      if(value.signum()==0)continue;
      total=total.add(value);
      String asset=h.path("asset_type").asText();
      if("EQUITY".equals(asset)){
        directValue=directValue.add(value);
        String isin=h.path("isin").asText();
        if(equityIsin(isin)){
          direct.merge(isin,value,BigDecimal::add);
          var company=h.path("thesis_evidence").path("company_evidence");
          var profile=company.path("sections").path("profile");
          if(isin.equals(company.path("isin").asText())&&"AVAILABLE".equals(profile.path("status").asText())){
            var evidence=json.createObjectNode();
            evidence.set("sector",profile.path("data").path("sector"));
            evidence.set("provider",profile.path("source").path("provider"));
            evidence.set("retrieved_at",company.path("retrieved_at"));
            sectorEvidence(sectorLabels,isin,evidence,now);
          }
        }
      }else if("MUTUAL_FUND".equals(asset)){
        positiveFunds++;fundValue=fundValue.add(value);
        Composition c=composition(h,now,today);
        String code=h.path("exact_scheme_code").asText();
        if(c==null){conflicts.add(code);continue;}
        Fund old=funds.get(code);
        if(old!=null&&!old.composition().equals(c)){conflicts.add(code);continue;}
        funds.put(code,new Fund(c,old==null?value:old.value().add(value)));
        fundSectorEvidence.computeIfAbsent(code,k->new ArrayList<>()).add(h.path("fund_thesis_evidence").path("portfolio").path("exact_sector_evidence"));
      }else{out.put("status","UNSUPPORTED_ASSET_TYPE");return out;}
    }
    if(positiveFunds==0){out.put("status","NO_POSITIVE_FUND_HOLDINGS");return out;}
    conflicts.forEach(funds::remove);
    if(funds.isEmpty()){out.put("status","NO_MATCHED_FUND_COMPOSITION");return out;}
    LocalDate cohort=funds.values().stream().map(f->f.composition().date()).max(Comparator.naturalOrder()).orElseThrow();
    var selected=funds.values().stream().filter(f->f.composition().date().equals(cohort)).toList();
    // Multiple schemes of the same underlying fund must agree on the full reported weights.
    Map<String,Composition> underlying=new HashMap<>();Set<String> inconsistent=new HashSet<>();
    for(Fund f:selected){
      Composition c=f.composition(),old=underlying.putIfAbsent(c.fundId(),c);
      if(old!=null&&!old.weights().equals(c.weights()))inconsistent.add(c.fundId());
    }
    selected=selected.stream().filter(f->!inconsistent.contains(f.composition().fundId())).toList();
    if(selected.isEmpty()){out.put("status","NO_MATCHED_FUND_COMPOSITION");return out;}
    Map<String,BigDecimal> indirect=new TreeMap<>();Map<String,Integer> contributors=new TreeMap<>();
    BigDecimal matchedFundValue=ZERO;
    for(Fund f:selected){
      matchedFundValue=matchedFundValue.add(f.value());
      for(JsonNode evidence:fundSectorEvidence.getOrDefault(f.composition().code(),List.of()))
        for(String isin:f.composition().weights().keySet())sectorEvidence(sectorLabels,isin,evidence.path(isin),now);
      f.composition().weights().forEach((isin,w)->{
        indirect.merge(isin,f.value().multiply(w).movePointLeft(2),BigDecimal::add);
        contributors.merge(isin,1,Integer::sum);
      });
    }
    var all=new TreeSet<>(direct.keySet());all.addAll(indirect.keySet());
    List<Exposure> exposures=new ArrayList<>();
    List<PortfolioLevelRisk.Attention> risk=new ArrayList<>();
    for(String isin:all){
      BigDecimal d=direct.getOrDefault(isin,ZERO),i=indirect.getOrDefault(isin,ZERO),v=d.add(i);
      exposures.add(new Exposure(isin,money(d),money(i),money(v),pct(v,total),contributors.getOrDefault(isin,0)));
      // Only flag hidden threshold crossings, not concentration already visible in direct holdings.
      if(i.signum()>0&&d.multiply(HUNDRED).compareTo(total.multiply(BigDecimal.valueOf(25)))<=0&&
          v.multiply(HUNDRED).compareTo(total.multiply(BigDecimal.valueOf(25)))>0)
        risk.add(new PortfolioLevelRisk.Attention("HIDDEN_EQUITY_CONCENTRATION",isin+" combined equity exposure",
          pct(v,total).doubleValue(),25,"PERCENT",cohort.toString()));
    }
    exposures.sort(Comparator.comparing(Exposure::estimatedValue).reversed().thenComparing(Exposure::isin));
    BigDecimal mapped=direct.values().stream().reduce(ZERO,BigDecimal::add).add(indirect.values().stream().reduce(ZERO,BigDecimal::add));
    Map<String,BigDecimal> directSectors=new TreeMap<>(),indirectSectors=new TreeMap<>();
    for(String isin:all){
      Set<String> labels=sectorLabels.getOrDefault(isin,Set.of());
      if(labels.size()!=1)continue;
      String sector=labels.iterator().next();
      directSectors.merge(sector,direct.getOrDefault(isin,ZERO),BigDecimal::add);
      indirectSectors.merge(sector,indirect.getOrDefault(isin,ZERO),BigDecimal::add);
    }
    List<Sector> sectorRows=new ArrayList<>();BigDecimal classified=ZERO;
    for(String sector:directSectors.keySet()){
      BigDecimal d=directSectors.get(sector),i=indirectSectors.get(sector),v=d.add(i);
      classified=classified.add(v);
      sectorRows.add(new Sector(sector,money(d),money(i),money(v),pct(v,total),
        v.multiply(HUNDRED).compareTo(total.multiply(BigDecimal.valueOf(40)))>0));
    }
    sectorRows.sort(Comparator.comparing(Sector::estimatedValue).reversed().thenComparing(Sector::sector));
    out.put("sector_status",classified.signum()>0?"PARTIAL_CLASSIFIED_EXPOSURE":"NO_CURRENT_EXACT_CLASSIFICATION");
    out.put("sector_classified_portfolio_percent",pct(classified,total));
    out.put("sector_classified_value",money(classified));
    out.put("sector_unclassified_mapped_value",money(mapped.subtract(classified)));
    out.put("sector_exposures",sectorRows.stream().limit(20).toList());
    out.put("sector_count",sectorRows.size());
    out.put("sector_review_count",sectorRows.stream().filter(Sector::reviewConcentration).count());
    out.put("sector_notice","Sector weights use the entire recorded portfolio, not only classified equity. Fresh provider labels may be incomplete or inconsistent; unknown exposures are not assigned to sectors. Above 40% is an illustrative review observation, not a personalized target.");
    List<Pair> pairs=new ArrayList<>();
    for(int a=0;a<selected.size();a++)for(int b=a+1;b<selected.size();b++){
      Composition x=selected.get(a).composition(),y=selected.get(b).composition();
      if(x.coverage().compareTo(BigDecimal.valueOf(80))<0||y.coverage().compareTo(BigDecimal.valueOf(80))<0)continue;
      var common=new HashSet<>(x.weights().keySet());common.retainAll(y.weights().keySet());
      BigDecimal shared=common.stream().map(k->x.weights().get(k).min(y.weights().get(k))).reduce(ZERO,BigDecimal::add);
      pairs.add(new Pair(x.code(),y.code(),x.fundId().equals(y.fundId()),common.size(),money(shared),money(x.coverage()),money(y.coverage())));
      if(shared.compareTo(BigDecimal.valueOf(50))>=0)
        risk.add(new PortfolioLevelRisk.Attention("HIGH_FUND_OVERLAP",x.code()+" / "+y.code()+
          (x.fundId().equals(y.fundId())?" (same underlying fund)":" shared equity weight"),
          money(shared).doubleValue(),50,"PERCENT",cohort.toString()));
    }
    pairs.sort(Comparator.comparing(Pair::sharedWeightPercent).reversed().thenComparing(Pair::schemeA).thenComparing(Pair::schemeB));
    out.put("status","DATED_PARTIAL_EQUITY_EXPOSURE_ESTIMATE");
    out.put("portfolio_date",cohort.toString());out.put("recorded_value",money(total));
    out.put("fund_value",money(fundValue));out.put("matched_fund_value",money(matchedFundValue));
    out.put("matched_fund_value_percent",pct(matchedFundValue,fundValue));
    out.put("direct_equity_value",money(directValue));out.put("mapped_equity_value",money(mapped));
    out.put("mapped_portfolio_percent",pct(mapped,total));out.put("unmodeled_value",money(total.subtract(mapped)));
    out.put("matched_scheme_count",selected.size());out.put("mapped_equity_count",exposures.size());
    out.put("overlap_pair_count",pairs.size());out.put("exposures",exposures.stream().limit(20).toList());
    out.put("overlap_pairs",pairs.stream().limit(20).toList());
    risk.sort(Comparator.comparing(PortfolioLevelRisk.Attention::kind).thenComparing(Comparator.comparingDouble(PortfolioLevelRisk.Attention::value).reversed()).thenComparing(PortfolioLevelRisk.Attention::label));
    out.put("risk_observation_count",risk.size());out.put("risk_observations",risk.stream().limit(20).toList());
    return out;
  }

  /** Full source weights are internal working evidence, not an expanded public API payload. */
  static void stripWorkingWeights(List<Map<String,Object>> holdings){
    for(var h:holdings)if(h.get("fund_thesis_evidence") instanceof JsonNode node&&
        node.path("portfolio") instanceof com.fasterxml.jackson.databind.node.ObjectNode p){p.remove("exact_equity_weights");p.remove("exact_sector_evidence");}
  }
}
