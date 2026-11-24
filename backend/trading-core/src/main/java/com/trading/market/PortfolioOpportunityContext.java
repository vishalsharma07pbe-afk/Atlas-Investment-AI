package com.trading.market;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.*;

/** Compare a public watch projection with owner-local resolved holdings; no portfolio data leaves Spring. */
final class PortfolioOpportunityContext {
 private PortfolioOpportunityContext(){}
 private static final Map<String,String> CATEGORIES=Map.of("LARGE_CAP","large cap fund","MID_CAP","mid cap fund",
   "SMALL_CAP","small cap fund","FLEXI_CAP","flexi cap fund","INDEX","index funds");

 static Map<String,Object> compare(List<Map<String,Object>> holdings,Map<String,Object> diversification,JsonNode snapshot,ObjectMapper json){
  Set<String> equityIds=new HashSet<>(),fundIds=new HashSet<>(),fundCategories=new HashSet<>();
  boolean unknownEquity=false,unknownFund=false,unknownCategory=false;
  for(var holding:holdings){
   JsonNode h=json.valueToTree(holding);
   if("EQUITY".equals(h.path("asset_type").asText())){
    String isin=h.path("isin").asText();
    if(isin.matches("IN[A-Z0-9]{10}"))equityIds.add(isin);else unknownEquity=true;
   }else if("MUTUAL_FUND".equals(h.path("asset_type").asText())){
    String code=h.path("exact_scheme_code").asText();
    if(code.matches("[0-9]{1,18}")&&code.equals(h.path("symbol").asText()))fundIds.add(code);else unknownFund=true;
    String category=label(h.path("scheme_category"));
    if(category.isBlank())unknownCategory=true;
    else for(var entry:CATEGORIES.entrySet())if(category.contains(" - "+entry.getValue()+")")||category.equals(entry.getValue()))fundCategories.add(entry.getKey());
   }
  }
  JsonNode exposure=json.valueToTree(diversification);
  List<Map<String,Object>> equities=new ArrayList<>(),funds=new ArrayList<>();
  Set<String> seen=new HashSet<>();
  int heldExcluded=0;
  for(JsonNode item:snapshot.path("equities")){
   String isin=item.path("isin").asText(),symbol=item.path("symbol").asText(),sector=label(item.path("sector"));
   if(!"TECHNICAL_WATCH_ONLY".equals(item.path("evidence_type").asText())||!isin.matches("IN[A-Z0-9]{10}")||symbol.isBlank()||!seen.add(isin))continue;
   if(equityIds.contains(isin)){heldExcluded++;continue;}
   Double weight=null;
   for(JsonNode group:exposure.path("direct_equity_sector_exposure"))if(!sector.isBlank()&&sector.equals(label(group.path("label")))&&group.path("weight_percent").isNumber())
     weight=group.path("weight_percent").asDouble();
   String context=sector.isBlank()?"SECTOR_UNKNOWN":weight!=null&&weight>40?"EXISTING_SECTOR_CONCENTRATION":
     weight!=null?"EXISTING_SECTOR_EXPOSURE":"NO_MATCH_IN_RECORDED_SECTORS";
   var out=new LinkedHashMap<String,Object>();
   out.put("symbol",symbol);out.put("isin",isin);out.put("exchange",item.path("exchange").asText());
   out.put("horizon",item.path("horizon").asText());out.put("as_of",item.path("as_of").asText());
   out.put("adjustment_status",item.path("adjustment_status").asText());out.put("blockers",item.path("blockers"));
   out.put("sector",sector.isBlank()?null:sector);out.put("sector_weight_percent",weight);out.put("context",context);
   out.put("identity_status",unknownEquity?"UNRESOLVED_HOLDINGS_EXIST":"NO_EXACT_HELD_IDENTITY_MATCH");
   out.put("evidence_type","TECHNICAL_WATCH_ONLY");equities.add(out);
  }
  seen.clear();
  for(JsonNode item:snapshot.path("funds")){
   String code=item.path("scheme_code").asText(),category=item.path("category").asText(),name=item.path("name").asText();
   if(!"HISTORICAL_WATCH_ONLY".equals(item.path("evidence_type").asText())||!code.matches("[0-9]{1,18}")
     ||!CATEGORIES.containsKey(category)||name.isBlank()||!seen.add(code))continue;
   if(fundIds.contains(code)){heldExcluded++;continue;}
   var out=new LinkedHashMap<String,Object>();
   out.put("scheme_code",code);out.put("name",name);out.put("category",category);out.put("as_of",item.path("as_of").asText());
   out.put("cagr_3y_percent",item.path("cagr_3y_percent"));out.put("drawdown_3y_percent",item.path("drawdown_3y_percent"));
   out.put("context",fundCategories.contains(category)?"EXISTING_FUND_CATEGORY":unknownCategory?"CATEGORY_COVERAGE_INCOMPLETE":"NO_MATCH_IN_RECORDED_FUND_CATEGORIES");
   out.put("identity_status",unknownFund?"UNRESOLVED_HOLDINGS_EXIST":"NO_EXACT_HELD_IDENTITY_MATCH");
   out.put("evidence_type","HISTORICAL_WATCH_ONLY");funds.add(out);
  }
  String upstream=snapshot.path("status").asText("UNAVAILABLE");
  var result=new LinkedHashMap<String,Object>();
  result.put("status",!equities.isEmpty()||!funds.isEmpty()?"WATCH_CONTEXT_AVAILABLE":
    "WATCH_EVIDENCE_AVAILABLE".equals(upstream)?"NO_NEW_EXACT_IDENTITY_WATCHES":upstream);
  result.put("equities",equities);result.put("funds",funds);result.put("held_excluded_count",heldExcluded);
  result.put("ready_sections",snapshot.path("ready_sections").isArray()?snapshot.path("ready_sections"):List.of());
  result.put("blocked_sections",snapshot.path("blocked_sections").isArray()?snapshot.path("blocked_sections"):List.of());
  result.put("notice","Public research watches compared locally with recorded holdings. No match does not establish diversification, suitability or a buy opportunity. Sector values cover priced direct equities only; fund look-through, overlap, valuation and future returns are not verified. Original research gates remain unchanged.");
  return result;
 }
 private static String label(JsonNode n){
  if(!n.isTextual())return "";
  String s=n.asText().trim().replaceAll("\\s+"," ").toLowerCase(Locale.ROOT);
  return Set.of("unknown","n/a","na","not available","-").contains(s)?"":s;
 }
}
