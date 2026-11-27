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
    if(a==null||b==null||!(profitability?"PERCENT":"RATIO").equals(unit)||!unit.equals(r.path("sector_unit").asText()))continue;
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
   JsonNode trends=company.path("financial_trends");
   int trendCount=0;
   for(JsonNode trend:trends.path("items")){
    String metric=trend.path("metric").asText();
    String label=switch(metric){case "REVENUE"->"Revenue";case "NET_PROFIT"->"Net profit";case "OPERATING_PROFIT"->"Operating profit";
      case "OPERATING_CASH_FLOW"->"Operating cash flow";case "TOTAL_ASSETS"->"Total assets";
      case "TOTAL_LIABILITIES"->"Total liabilities";default->null;};
    Double previous=number(trend,"previous_value"),latest=number(trend,"latest_value");
    int start=trend.path("previous_year").asInt(),end=trend.path("latest_year").asInt();
    String unit=trend.path("unit").asText();
    if(label==null||previous==null||latest==null||start<2000||end-start!=1||unit.isBlank())continue;
    if(trend.path("latest_period_may_be_stale").asBoolean(true))continue;
    trendCount++;
    String statement=label+" "+trend.path("previous_period").asText("FY"+start)+" "+fmt(previous)+" to "+trend.path("latest_period").asText("FY"+end)+" "+fmt(latest)+" ("+unit+").";
    Double change=number(trend,"change_percent");
    if(change!=null)statement+=" Reported annual change "+fmt(change)+"%.";
    boolean operating=Set.of("REVENUE","NET_PROFIT","OPERATING_PROFIT","OPERATING_CASH_FLOW").contains(metric);
    if(operating&&(latest<previous||latest<0))
      add(review,statement+" Investigate the reported deterioration or negative value.","Upstox consolidated yearly statements; filings unverified");
    else add(observations,statement+" Historical observation only.","Upstox consolidated yearly statements; filings unverified");
   }
   if(trendCount==0)gaps.add("Recent, consecutive annual financial statement comparisons unavailable.");
   else if(!"AVAILABLE".equals(trends.path("status").asText())||trendCount<trends.path("items").size())
     gaps.add("Annual financial statement coverage is partial; some metrics or recent periods are unavailable.");
   JsonNode quality=company.path("fundamental_quality");
   for(JsonNode metric:quality.path("derived_metrics")){
    String key=metric.path("metric").asText();
    if(!Set.of("NET_MARGIN","OPERATING_MARGIN","OPERATING_CASH_TO_PROFIT","REPORTED_LIABILITIES_TO_ASSETS").contains(key))continue;
    Double previous=number(metric,"previous_value"),latest=number(metric,"latest_value");
    if(previous==null||latest==null)continue;
    String label=switch(key){case "NET_MARGIN"->"Net margin";case "OPERATING_MARGIN"->"Operating margin";case "OPERATING_CASH_TO_PROFIT"->"Operating cash/profit";default->"Reported liabilities/assets";};
    String suffix="PERCENT".equals(metric.path("unit").asText())?"%":"x";
    String statement=label+" changed from "+fmt(previous)+suffix+" to "+fmt(latest)+suffix+" in matched annual periods.";
    boolean reviewMetric=!"REPORTED_LIABILITIES_TO_ASSETS".equals(key)&&(latest<previous||latest<0);
    add(reviewMetric?review:observations,statement,"Upstox matched annual statements; filings unverified");
   }
   // The shared company adapter has already matched reported consolidated
   // quarter periods. Preserve its limitations and never infer growth from gaps.
   JsonNode quarterly=company.path("quarterly_financials");
   String quarterStatus=quarterly.path("status").asText();
   int quarterCount=0;
   String isin=row.path("isin").asText();
   boolean recentQuarter=false;
   try{
     var period=java.time.LocalDate.parse(quarterly.path("latest_period").asText());
     long age=java.time.temporal.ChronoUnit.DAYS.between(period,java.time.LocalDate.now(java.time.ZoneId.of("Asia/Kolkata")));
     recentQuarter=age>=0&&age<=150&&period.getDayOfMonth()==period.lengthOfMonth();
   }catch(java.time.DateTimeException ignored){/* No dated quarter. */}
   if(isin.matches("IN[A-Z0-9]{10}")&&isin.equals(company.path("isin").asText())&&recentQuarter
       &&Set.of("REPORTED_QUARTERLY_COMPARISONS","PARTIAL_LATEST_QUARTER").contains(quarterStatus)){
     Map<String,List<JsonNode>> quarterMetrics=new TreeMap<>();
     for(JsonNode metric:quarterly.path("items")){
       String key=metric.path("metric").asText();
       if(Set.of("revenue","operating_profit","net_profit").contains(key))
         quarterMetrics.computeIfAbsent(key,k->new ArrayList<>()).add(metric);
     }
     for(var entry:quarterMetrics.entrySet()){
       if(entry.getValue().size()!=1)continue;
       JsonNode metric=entry.getValue().getFirst();
       Double latest=number(metric,"latest_value"),yoy=number(metric,"year_over_year_growth_percent"),
         qoq=number(metric,"previous_quarter_growth_percent"),acceleration=number(metric,"growth_acceleration_pp");
       if(latest==null||Math.abs(latest)>1e12)continue;
       if(yoy!=null&&(yoy< -100||yoy>1e12))yoy=null;
       if(qoq!=null&&(qoq< -100||qoq>1e12))qoq=null;
       if(acceleration!=null&&(Math.abs(acceleration)>2e12||yoy==null))acceleration=null;
       if(yoy==null&&qoq==null&&latest>=0)continue;
       quarterCount++;
       String label=switch(entry.getKey()){case "revenue"->"Revenue";case "operating_profit"->"Operating profit";default->"Net profit";};
       String statement=label+" quarter ended "+quarterly.path("latest_period").asText()+":";
       if(yoy!=null)statement+=" YoY "+fmt(yoy)+"%.";
       if(qoq!=null)statement+=" QoQ "+fmt(qoq)+"%.";
       if(acceleration!=null)statement+=" YoY growth acceleration "+fmt(acceleration)+" pp.";
       if(latest<0)statement+=" Negative reported value.";
       boolean concern=latest<0||(yoy!=null&&yoy<0)||(acceleration!=null&&acceleration<0);
       add(concern?review:observations,statement+(concern?" Reassess reported earnings direction; not an exit signal.":" Historical observation, not a forecast."),
           "Upstox consolidated quarterly statements; independent filings unverified");
     }
   }
   if(quarterCount<3||!"REPORTED_QUARTERLY_COMPARISONS".equals(quarterStatus))
     gaps.add("Recent matched quarterly revenue and profit comparisons are incomplete or unavailable.");
   JsonNode news=thesis.path("news_evidence");
   SortedSet<String> topics=new TreeSet<>();
   for(JsonNode article:news.path("articles"))for(JsonNode topic:article.path("topics"))
     if(TOPICS.contains(topic.asText()))topics.add(topic.asText());
   if(!topics.isEmpty())add(review,"Recent headline topics: "+String.join(", ",topics)+". Open source headlines to verify the events.","Upstox News; headline matches only");
   if(!Set.of("REVIEW_AVAILABLE","NO_RECENT_RETURNED_ARTICLES").contains(news.path("status").asText()))
     gaps.add("Usable recent company news coverage is unavailable.");
   JsonNode ownership=company.path("ownership_research");
   if("COMPARABLE_QUARTERS".equals(ownership.path("status").asText())){
    for(JsonNode prompt:ownership.path("review_prompts")){
      String category=prompt.path("category").asText();
      Double change=number(prompt,"change_pp");
      if(Set.of("promoters","fii","other_dii","mutual_funds").contains(category)&&change!=null&&change<=-1&&change>=-100){
        add(review,"Reported "+category.replace('_',' ')+" ownership fell "+fmt(-change)+" percentage points between "+ownership.path("previous_period").asText()+" and "+ownership.path("latest_period").asText()+". Verify the filing and share-count changes; this is not proof of sales.",
          "Upstox quarterly shareholding; official filing unverified");
      }
    }
   }else gaps.add("Comparable complete quarterly ownership reports unavailable.");
   gaps.add("Official filings, comparable financial periods, intrinsic valuation and company-specific institutional flows remain unverified.");
   gaps.add("Promoter pledges and bulk/block transactions remain unverified; ownership changes do not establish stock-specific trades.");
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
   JsonNode evidence=row.path("fund_thesis_evidence"),disclosure=evidence.path("disclosure"),composition=evidence.path("portfolio");
   if("SECONDARY_REPORTED_EVIDENCE".equals(evidence.path("status").asText())){
    String disclosureSource="Secondary AMFI-derived disclosure; not independently verified";
    Double ter=number(disclosure,"ter_percent");
    if(ter!=null&&ter>=0&&ter<=100)add(observations,"Reported plan TER: "+fmt(ter)+"% as of "+disclosure.path("ter_date").asText()+".",disclosureSource);
    String risk=disclosure.path("riskometer").asText();
    if(Set.of("LOW","LOW_TO_MODERATE","MODERATE","MODERATELY_HIGH","HIGH","VERY_HIGH").contains(risk)){
      add(Set.of("HIGH","VERY_HIGH").contains(risk)?review:observations,"Reported Riskometer: "+risk.replace('_',' ')+". Review suitability against your investment horizon and tolerance.",disclosureSource);
    }
    for(JsonNode conflict:disclosure.path("conflicts"))if(Set.of("BENCHMARK_CONFLICT","RISKOMETER_CONFLICT").contains(conflict.asText()))
      gaps.add("Conflicting secondary disclosure: "+conflict.asText()+".");
    JsonNode underlying=composition.path("underlying_research");
    Double covered=number(underlying,"annual_statement_weight_percent"),flagged=number(underlying,"deterioration_review_weight_percent");
    if("SECONDARY_COMPOSITION_ONLY".equals(composition.path("status").asText())&&
      "REPORTED_HISTORICAL_DRIVERS_ONLY".equals(underlying.path("status").asText())&&
      covered!=null&&flagged!=null&&covered>0&&covered<=100.5&&flagged>=0&&flagged<=covered){
      String statement=fmt(flagged)+"% of reported fund weight has underlying annual financial deterioration observations; "+fmt(covered)+"% has annual statement evidence. Uncovered holdings are unknown.";
      add(flagged>=20?review:observations,statement,"Secondary AMC-derived holdings and cached historical company reports; portfolio dated "+composition.path("portfolio_date").asText());
    }else gaps.add("Comparable underlying company financial evidence is unavailable or incomplete.");
   }else gaps.add("No current exact-scheme secondary disclosure match.");
   gaps.add("Official benchmark TRI history, primary expenses, holdings overlap and Riskometer remain independently unverified.");
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
