package com.trading.market;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.*;

/** Local evidence synthesis. No model calls, predictions or trade instructions. */
final class PortfolioThesisSummary {
 private PortfolioThesisSummary(){}
 private static final Map<String,String> RATIOS=Map.ofEntries(
   Map.entry("p/e","PE"),Map.entry("pe","PE"),Map.entry("price to earnings","PE"),
   Map.entry("p/b","PB"),Map.entry("price to book","PB"),
   Map.entry("roe","ROE"),Map.entry("return on equity","ROE"),
   Map.entry("roce","ROCE"),Map.entry("return on capital employed","ROCE"),
   Map.entry("debt to equity","DEBT_EQUITY"),Map.entry("debt/equity","DEBT_EQUITY"));
 private static final Set<String> TOPICS=Set.of("EARNINGS","REGULATORY","CORPORATE_ACTION","TRANSACTION","MANAGEMENT");

 static Map<String,Object> summarize(Map<String,Object> holding,ObjectMapper json){
  JsonNode row=json.valueToTree(holding);
  List<Map<String,String>> risks=new ArrayList<>(),observations=new ArrayList<>(),review=new ArrayList<>();
  List<String> gaps=new ArrayList<>();
  for(JsonNode f:row.path("findings"))if(f.isTextual())
    add(risks,f.asText(),"Local portfolio review");
  if("EQUITY".equals(row.path("asset_type").asText())){
   JsonNode thesis=row.path("thesis_evidence"),company=thesis.path("company_evidence");
   JsonNode sections=company.path("sections");
   Map<String,List<JsonNode>> recognized=new TreeMap<>();
   for(JsonNode ratio:sections.path("ratios").path("data")){
    String key=RATIOS.get(ratio.path("name").asText().trim().toLowerCase(Locale.ROOT));
    if(key!=null)recognized.computeIfAbsent(key,k->new ArrayList<>()).add(ratio);
   }
   int comparisons=0;
   for(var entry:recognized.entrySet()){
    // Duplicate aliases may describe different periods. Never choose one silently.
    if(entry.getValue().size()!=1)continue;
    JsonNode r=entry.getValue().getFirst();String key=entry.getKey();
    Double a=number(r,"company_value"),b=number(r,"sector_value");
    String unit=r.path("unit").asText();
    boolean profitability=Set.of("ROE","ROCE").contains(key);
    if(a==null||b==null||!(profitability?"PERCENT":"RATIO").equals(unit))continue;
    if(!profitability&&(a<=0||b<=0))continue;
    comparisons++;
    String label=switch(key){case "PE"->"P/E";case "PB"->"P/B";case "DEBT_EQUITY"->"Debt/equity";default->key;};
    String suffix=profitability?"%":"";
    String statement=label+" "+fmt(a)+suffix+" vs sector "+fmt(b)+suffix+".";
    String source="Upstox provider ratios; observation period unverified";
    if((profitability&&a<b)||(!profitability&&a>b))
      add(review,statement+" Review comparability and underlying financials.",source);
    else add(observations,statement+" Not evidence of fair value or future growth.",source);
   }
   if(comparisons==0)gaps.add("No unambiguous, unit-matched company/sector ratio comparison.");
   JsonNode news=thesis.path("news_evidence");
   SortedSet<String> topics=new TreeSet<>();
   for(JsonNode article:news.path("articles"))for(JsonNode topic:article.path("topics"))
     if(TOPICS.contains(topic.asText()))topics.add(topic.asText());
   if(!topics.isEmpty())add(review,"Recent headline topics: "+String.join(", ",topics)+". Open source headlines to verify the events.","Upstox News; headline matches only");
   if(!Set.of("REVIEW_AVAILABLE","NO_RECENT_RETURNED_ARTICLES").contains(news.path("status").asText()))
     gaps.add("Usable recent company news coverage is unavailable.");
   gaps.add("Official filings, comparable financial periods, intrinsic valuation and company-specific institutional flows remain unverified.");
  }else if("MUTUAL_FUND".equals(row.path("asset_type").asText())){
   JsonNode history=row.path("fund_history_evidence");
   Double cagr=number(history,"cagr_3y_percent"),drawdown=number(history,"drawdown_3y_percent"),vol=number(history,"weekly_volatility_percent");
   String source="Exact-scheme AMFI/MFAPI NAV history";
   if(cagr!=null){
    String statement="Observed three-year CAGR: "+fmt(cagr)+"%. Historical returns do not predict future results.";
    add(cagr<0?review:observations,statement,source);
   }else gaps.add("Validated three-year exact-scheme NAV history is unavailable.");
   if(drawdown!=null&&drawdown<=0&&drawdown>=-100){
    String statement="Observed three-year maximum drawdown: "+fmt(drawdown)+"%.";
    add(drawdown<=-20?review:observations,statement+(drawdown<=-20?" Review tolerance for a 20% or greater historical decline.":""),source);
   }
   if(vol!=null&&vol>=0)add(observations,"Annualized weekly volatility proxy: "+fmt(vol)+"%.",source);
   gaps.add("Official benchmark TRI, expenses, holdings overlap and Riskometer remain unverified.");
  }else gaps.add("Unsupported holding type for thesis evidence.");
  for(JsonNode m:row.path("missing_evidence"))if(m.isTextual()){
   String detail=m.asText();
   if(!detail.startsWith("Current fundamentals,")&&!detail.startsWith("Fund holdings,"))gaps.add(detail);
  }
  String status=!risks.isEmpty()||!review.isEmpty()?"REVIEW_EVIDENCE":"INSUFFICIENT_FOR_VERDICT";
  Map<String,Object> result=new LinkedHashMap<>();
  result.put("status",status);result.put("risks",risks);result.put("observations",observations);
  result.put("review_prompts",review);result.put("gaps",gaps);
  result.put("notice","Partial research synthesis, not an investment verdict, prediction or instruction. Missing evidence is not a positive signal.");
  return result;
 }

 private static void add(List<Map<String,String>> rows,String statement,String source){
  rows.add(Map.of("statement",statement,"source",source));
 }
 private static Double number(JsonNode row,String key){
  JsonNode value=row.path(key);
  return value.isNumber()&&Double.isFinite(value.asDouble())?value.asDouble():null;
 }
 private static String fmt(double value){return String.format(Locale.ROOT,"%.2f",value);}
}
