package com.trading.market;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.*;

/** Owner-local, explicit evidence rubric. Scores are not comparable across asset classes. */
final class PortfolioReassessment {
 private PortfolioReassessment(){}
 static final String NOTICE="Illustrative directional research rubric, not the Elite score, a calibrated rating, expected return, suitability or a buy/sell instruction. Missing factors withhold the score. No cross-asset score averaging.";
 private static Double number(JsonNode n,String key){var v=n.path(key);return v.isNumber()&&Double.isFinite(v.asDouble())?v.asDouble():null;}
 private static boolean recent(String value,LocalDate today,int max){
  try{long age=ChronoUnit.DAYS.between(LocalDate.parse(value),today);return age>=0&&age<=max;}catch(java.time.DateTimeException ex){return false;}
 }
 private static double scale(double v,double low,double high){return Math.max(0,Math.min(1,(v-low)/(high-low)));}
 private static void factor(Map<String,Double> f,String name,Double value,double lo,double hi){
  f.put(name,value==null?null:Math.round(25*scale(value,lo,hi)*100d)/100d);
 }
 private static Double quarter(JsonNode report,String metric){
  List<JsonNode> found=new ArrayList<>();
  for(var item:report.path("items"))if(metric.equals(item.path("metric").asText()))found.add(item);
  if(found.size()!=1)return null;
  Double latest=number(found.getFirst(),"latest_value"),yoy=number(found.getFirst(),"year_over_year_growth_percent");
  if(latest==null||Math.abs(latest)>1e12)return null;
  if(latest<0)return -20d;
  return yoy!=null&&yoy>=-100&&yoy<=1e12?yoy:null;
 }
 static Map<String,Object> holding(Map<String,Object> row,ObjectMapper json,LocalDate today){
  JsonNode h=json.valueToTree(row),company=h.path("thesis_evidence").path("company_evidence");
  Map<String,Double> factors=new LinkedHashMap<>();
  String type=h.path("asset_type").asText(),method="UNSUPPORTED";
  if("EQUITY".equals(type)){
   method="HELD_EQUITY_DIRECTIONAL_1";
   String isin=h.path("isin").asText();
   boolean identity=isin.matches("INE[A-Z0-9]{9}")&&isin.equals(company.path("isin").asText());
   var q=company.path("quarterly_financials");
   boolean quarter=identity&&recent(q.path("latest_period").asText(),today,150)
      &&Set.of("REPORTED_QUARTERLY_COMPARISONS","PARTIAL_LATEST_QUARTER").contains(q.path("status").asText());
   factor(factors,"QUARTERLY_REVENUE_YOY",quarter?quarter(q,"revenue"):null,-10,20);
   factor(factors,"QUARTERLY_NET_PROFIT_YOY",quarter?quarter(q,"net_profit"):null,-20,30);
   Double cash=null;
   var quality=company.path("fundamental_quality");
   if(identity){
    List<JsonNode> matched=new ArrayList<>();
    for(var m:quality.path("derived_metrics"))if("OPERATING_CASH_TO_PROFIT".equals(m.path("metric").asText()))matched.add(m);
    if(matched.size()==1){
     var metric=matched.getFirst();
     // Use a ratio only with a recent dated matched annual operating cash/profit observation.
     var annual=company.path("financial_trends");
     Set<String> current=new HashSet<>();
     for(var trend:annual.path("items"))if(Set.of("NET_PROFIT","OPERATING_CASH_FLOW").contains(trend.path("metric").asText())
       &&!trend.path("latest_period_may_be_stale").asBoolean(true)&&number(trend,"latest_value")!=null
       &&number(trend,"latest_value")>0)current.add(trend.path("metric").asText()+":"+trend.path("latest_year").asText());
     for(String key:current)if(key.startsWith("NET_PROFIT:")&&key.substring("NET_PROFIT:".length()).equals(metric.path("latest_year").asText())&&"RATIO".equals(metric.path("unit").asText())&&current.contains("OPERATING_CASH_FLOW:"+key.substring("NET_PROFIT:".length())))
       cash=number(metric,"latest_value");
    }
   }
   factor(factors,"REPORTED_ANNUAL_CASH_CONVERSION",cash,0.5,1.2);
   var relative=h.path("holding_relative_strength");
   var w=relative.path("windows").path("60");
   Double excess="MATCHED_PRICE_INDEX_OBSERVATIONS".equals(relative.path("status").asText())&&recent(w.path("last_date").asText(),today,5)?number(w,"difference_pp"):null;
   factor(factors,"MATCHED_60_SESSION_RELATIVE_RETURN",excess,-10,10);
  }else if("MUTUAL_FUND".equals(type)){
   method="HELD_EQUITY_FUND_HISTORY_1";
   var history=h.path("fund_history_evidence");var weekly=history.path("matched_weekly_comparison");
   String category=history.path("category").asText().toLowerCase(Locale.ROOT);
   boolean valid=h.path("exact_scheme_code").asText().matches("[1-9][0-9]{5,8}")
     &&h.path("exact_scheme_code").asText().equals(history.path("scheme_code").asText())
     &&history.path("isin_growth").asText().matches("INF[A-Z0-9]{9}")
     &&"GROWTH".equals(history.path("amfi_option").asText())&&category.contains("equity scheme")
     &&weekly.path("date_digest").asText().matches("[a-f0-9]{64}")
     &&"MF-WEEKLY-MATCH-1".equals(weekly.path("methodology").asText())&&weekly.path("anchor_count").asInt()==157
     &&recent(weekly.path("last_date").asText(),today,7);
   factor(factors,"MATCHED_WEEKLY_CAGR",valid?number(weekly,"cagr_percent"):null,0,20);
   factor(factors,"MATCHED_WEEKLY_DRAWDOWN",valid?number(weekly,"drawdown_percent"):null,-40,0);
   factor(factors,"WORST_ROLLING_YEAR",valid?number(history,"worst_rolling_52w_annualized_percent"):null,-20,15);
   Double vol=valid?number(history,"weekly_volatility_percent"):null;
   factor(factors,"LOWER_WEEKLY_VOLATILITY",vol==null||vol<0?null:-vol,-40,-10);
  }
  var components=new ArrayList<Map<String,Object>>();var missing=new ArrayList<String>();
  for(var entry:factors.entrySet()){
   var f=new LinkedHashMap<String,Object>();f.put("factor",entry.getKey());f.put("weight",25);f.put("points",entry.getValue());components.add(f);
   if(entry.getValue()==null)missing.add(entry.getKey());
  }
  boolean complete=factors.size()==4&&missing.isEmpty();
  Double score=complete?Math.round(factors.values().stream().mapToDouble(Double::doubleValue).sum()*100d)/100d:null;
  var thesis=h.path("thesis_summary");
  boolean attention="REVIEW_REQUIRED".equals(h.path("status").asText())||"REVIEW_EVIDENCE".equals(thesis.path("status").asText());
  // Research review always takes precedence over even a strong historical score.
  String decision=attention?"REASSESS_EVIDENCE":!complete?"COLLECT_EVIDENCE":"MONITOR_RESEARCH_ONLY";
  var out=new LinkedHashMap<String,Object>();out.put("methodology",method);out.put("status",complete?"PRELIMINARY_SCORE_ONLY":"SCORE_WITHHELD");
  out.put("score",score);out.put("components",components);out.put("missing_factors",missing);out.put("review_state",decision);
  out.put("qualified",false);out.put("notice",NOTICE);return out;
 }
 static Map<String,Object> synthesis(List<Map<String,Object>> holdings,ObjectMapper json){
  int scored=0,review=0,missing=0,monitor=0;
  for(var h:holdings){
   JsonNode a=json.valueToTree(h.get("reassessment"));
   if(a.path("score").isNumber())scored++;
   switch(a.path("review_state").asText()){
    case "REASSESS_EVIDENCE"->review++;
    case "MONITOR_RESEARCH_ONLY"->monitor++;
    default->missing++;
   }
  }
  return Map.of("status",holdings.isEmpty()?"NO_HOLDINGS":review>0?"REASSESS_EVIDENCE":missing>0?"EVIDENCE_INCOMPLETE":"MONITOR_RESEARCH_ONLY",
   "holding_count",holdings.size(),"scored_count",scored,"reassess_count",review,"evidence_needed_count",missing,"monitor_count",monitor,
   "notice",NOTICE);
 }
}
