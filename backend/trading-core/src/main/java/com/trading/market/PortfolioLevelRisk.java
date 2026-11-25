package com.trading.market;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.LocalDate;
import java.util.*;

/** Deterministic portfolio-level research prompts, using existing evidence only. */
final class PortfolioLevelRisk {
  private PortfolioLevelRisk(){}
  record Attention(String kind,String label,double value,double threshold,String unit,String evidenceThrough){}
  private static Double number(JsonNode row,String field){
    JsonNode n=row.path(field);
    return n.isNumber()&&Double.isFinite(n.asDouble())?n.asDouble():null;
  }
  private static LocalDate day(JsonNode row,String field){
    try{return LocalDate.parse(row.path(field).asText());}catch(RuntimeException ex){return null;}
  }

  static Map<String,Object> assess(Map<String,Object> report,ObjectMapper json,LocalDate today){
    JsonNode root=json.valueToTree(report);
    List<Attention> attention=new ArrayList<>();
    JsonNode benchmark=root.path("benchmark_risk_estimate");
    LocalDate through=day(benchmark,"through"),from=day(benchmark,"from");
    Double gap=number(benchmark,"relativePercentagePoints");
    boolean benchmarkReady="AVAILABLE_PRICE_REFERENCE_ESTIMATE".equals(benchmark.path("status").asText())
      &&benchmark.path("matchedWeeks").asInt()==13&&through!=null&&from!=null
      &&from.equals(through.minusWeeks(13))&&!through.isAfter(today)&&!through.isBefore(today.minusDays(7))
      &&gap!=null;
    if(benchmarkReady&&gap<=PortfolioBenchmarkRisk.REVIEW_GAP_PP&&"REVIEW_RELATIVE_LAG".equals(benchmark.path("attentionStatus").asText()))
      attention.add(new Attention("BENCHMARK_RELATIVE_LAG","13-week lag versus NIFTY 50 price index",gap,
        PortfolioBenchmarkRisk.REVIEW_GAP_PP,"PP",through.toString()));

    JsonNode holdings=root.path("holdings"),diversification=root.path("diversification");
    boolean valuationsComplete=holdings.isArray()&&!holdings.isEmpty();
    int positive=0;
    for(JsonNode h:holdings){
      Double value=number(h,"recorded_market_value");
      if(value==null||value<0||!h.path("recorded_valuation_recent").asBoolean(false))valuationsComplete=false;
      if(value!=null&&value>0)positive++;
    }
    // Single-position risk is already handled by the existing daily holding review.
    // For aggregate risk require at least two positive positions and exact identities.
    boolean concentrationReady=valuationsComplete&&positive>=2
      &&diversification.path("unpriced_count").asInt(-1)==0
      &&diversification.path("unresolved_identity_count").asInt(-1)==0
      &&diversification.path("resolved_identity_count").asInt(0)>=1
      &&diversification.path("concentration_observations").isArray();
    Double sectorCoverage=number(diversification,"sector_coverage_percent");
    if(concentrationReady){
      for(JsonNode flag:diversification.path("concentration_observations")){
        String type=flag.path("kind").asText(),label=flag.path("label").asText();
        Double weight=number(flag,"weight_percent");
        int threshold=switch(type){case "SINGLE_IDENTITY"->25;case "TOP_THREE"->60;case "DIRECT_EQUITY_SECTOR"->40;default->-1;};
        if(threshold<0||label.isBlank()||label.length()>200||weight==null||weight<threshold||weight>100)continue;
        if("DIRECT_EQUITY_SECTOR".equals(type)&&(sectorCoverage==null||sectorCoverage!=100.0))continue;
        // The upstream observation is evaluated before rounding; displayed weights can equal the threshold.
        attention.add(new Attention(type,label,weight,threshold,"PERCENT",today.toString()));
      }
    }
    JsonNode look=diversification.path("look_through");
    LocalDate disclosure=day(look,"portfolio_date");
    boolean lookReady=valuationsComplete&&"DATED_PARTIAL_EQUITY_EXPOSURE_ESTIMATE".equals(look.path("status").asText())
      &&disclosure!=null&&!disclosure.isAfter(today)&&!disclosure.isBefore(today.minusDays(60))
      &&look.path("risk_observations").isArray();
    if(lookReady){
      for(JsonNode flag:look.path("risk_observations")){
        String kind=flag.path("kind").asText(),label=flag.path("label").asText();
        int threshold=switch(kind){case "HIDDEN_EQUITY_CONCENTRATION"->25;case "HIGH_FUND_OVERLAP"->50;default->-1;};
        Double value=number(flag,"value");
        if(threshold<0||label.isBlank()||label.length()>200||value==null||value<threshold||value>100||
            !disclosure.toString().equals(flag.path("evidenceThrough").asText())||!"PERCENT".equals(flag.path("unit").asText()))continue;
        attention.add(new Attention(kind,label,value,threshold,"PERCENT",disclosure.toString()));
      }
    }
    var result=new LinkedHashMap<String,Object>();
    result.put("benchmark_status",benchmarkReady?"COMPARABLE_PRICE_REFERENCE":"INSUFFICIENT_EVIDENCE");
    result.put("concentration_status",concentrationReady?"RECENT_RECORDED_EXPOSURES":"INSUFFICIENT_EVIDENCE");
    result.put("sector_status",concentrationReady&&sectorCoverage!=null&&sectorCoverage==100.0?"CLASSIFIED_DIRECT_EQUITY":"INSUFFICIENT_EVIDENCE");
    result.put("look_through_status",lookReady?"DATED_PARTIAL_EQUITY_EXPOSURE_ESTIMATE":"INSUFFICIENT_EVIDENCE");
    result.put("attention",attention);
    result.put("notice","Benchmark comparison uses a price index, not TRI or a personalized benchmark. Direct concentration uses recent recorded values. Separate look-through flags use partial dated secondary fund weights, not live verified exposure. Review thresholds are illustrative, not trade instructions.");
    return result;
  }
}
