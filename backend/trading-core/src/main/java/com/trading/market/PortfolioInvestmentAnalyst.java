package com.trading.market;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.*;

/** Owner-local conditional holding decisions. Never sends or executes orders. */
final class PortfolioInvestmentAnalyst {
  private PortfolioInvestmentAnalyst(){}
  static final String VERSION="OWNER-INVESTMENT-ANALYST-1";
  static final String NOTICE="Conditional review plan from the recorded portfolio. No execution, fair-value certification, return forecast or personalized allocation amount. Do not sell solely because of price losses or buy solely because of historical returns.";
  private static Double numeric(JsonNode n,String k){
    var v=n.path(k);
    return v.isNumber()&&Double.isFinite(v.asDouble())?v.asDouble():null;
  }
  private static boolean recent(JsonNode h,LocalDate today){
    try{
      long age=ChronoUnit.DAYS.between(LocalDate.parse(h.path("evidence_date").asText()),today);
      return age>=0&&age<=("MUTUAL_FUND".equals(h.path("asset_type").asText())?7:5);
    }catch(java.time.DateTimeException ex){return false;}
  }
  private static boolean changed(JsonNode h){
    for(String field:List.of("ownership_changes","fund_thesis_changes","thesis_changes"))
      for(var item:h.path(field))
        if("REVIEW".equals(item.path("attention").asText())||
          ("thesis_changes".equals(field)&&Set.of("NEGATIVE","DECLINING").contains(item.path("current_direction").asText())))return true;
    return false;
  }
  private static boolean reason(JsonNode h){
    var summary=h.path("thesis_summary");
    return "REVIEW_EVIDENCE".equals(summary.path("status").asText())||changed(h);
  }
  static Map<String,Object> holding(JsonNode h,LocalDate today,boolean coverage){
    String type=h.path("asset_type").asText();
    var reassessment=h.path("reassessment");
    Double weight=numeric(h,"weight_percent"),score=numeric(reassessment,"score");
    boolean current=recent(h,today)&&h.path("recorded_valuation_recent").asBoolean(false);
    boolean complete="PRELIMINARY_SCORE_ONLY".equals(reassessment.path("status").asText())
       &&score!=null&&score>=0&&score<=100&&reassessment.path("missing_factors").isArray()
       &&reassessment.path("missing_factors").isEmpty();
    boolean concentrated=coverage&&weight!=null&&weight>=25&&weight<=100;
    boolean businessRisk=reason(h);
    boolean review="REVIEW_REQUIRED".equals(h.path("status").asText())||
      "REASSESS_EVIDENCE".equals(reassessment.path("review_state").asText());
    String action;String next;List<String> reasons=new ArrayList<>();
    if(businessRisk){
      action="REVIEW_REDUCTION";
      reasons.add("A reported business, ownership or fund thesis change warrants reassessment.");
      next="Verify the adverse change against the latest official evidence. If the original thesis is impaired, compare reducing exposure with retaining the holding after taxes and costs.";
    }else if(concentrated){
      action="REBALANCE_REVIEW";
      reasons.add(String.format(Locale.ROOT,"Recorded position is %.1f%% of the portfolio; the 25%% concentration review threshold is illustrative.",weight));
      next="Avoid increasing this concentration until reviewing correlated and underlying fund exposure. Compare using new contributions to diversify before considering a sale.";
    }else if(review){
      action="PAUSE_ADDITIONS";
      reasons.add("The existing holding review has a risk finding; a price decline alone does not establish business impairment.");
      next="Verify the risk finding and the latest investment thesis before increasing the position. Do not infer an exit from the recorded loss.";
    }else if(!current||!coverage||!complete){
      action="HOLD_PENDING_EVIDENCE";
      if(!current)reasons.add("Current dated holding evidence or recent recorded valuation is missing.");
      if(!coverage)reasons.add("Portfolio weights are not fully supported by recent recorded valuations.");
      if(!complete)reasons.add("The directional holding rubric has missing evidence.");
      next="Defer a new allocation decision until the missing evidence is available; do not interpret missing data as proof of a healthy holding.";
    }else if(score<35){
      action="REASSESS_THESIS";
      reasons.add(String.format(Locale.ROOT,"Complete preliminary directional score %.1f/100 is weak under the current rubric.",score));
      next="Compare the original thesis, recent business or fund performance and alternative investments before deciding whether to trim.";
    }else if(score>=75&&"EQUITY".equals(type)){
      action="COMPARE_FOR_ACCUMULATION";
      reasons.add(String.format(Locale.ROOT,"Preliminary business and relative-strength score %.1f/100 with no current recorded review finding.",score));
      next="Consider adding only if independent valuation, latest filings, liquidity and portfolio exposure support the case. A strong score is not a buy instruction.";
    }else{
      action="HOLD_MONITOR";
      reasons.add(String.format(Locale.ROOT,"Complete preliminary directional score %.1f/100; no current recorded review finding.",score));
      next="Maintain the research watch and revisit on new evidence. For funds, compare current official costs, holdings and horizon before changing the SIP.";
    }
    return Map.of("action",action,"reasons",reasons,"next_move",next,"qualified",false,
        "methodology",VERSION);
  }
  static Map<String,Object> attach(Map<String,Object> report,ObjectMapper json,LocalDate today){
    var out=new LinkedHashMap<>(report);
    JsonNode root=json.valueToTree(report);
    var holdings=root.path("holdings");
    boolean coverage=holdings.isArray()&&!holdings.isEmpty();
    double total=0;
    for(var h:holdings){
      Double w=numeric(h,"weight_percent");
      if(w==null||w<0||w>100||!h.path("recorded_valuation_recent").asBoolean(false))coverage=false;
      else total+=w;
    }
    coverage=coverage&&Math.abs(total-100)<=Math.max(.1,holdings.size()*.01);
    var counts=new LinkedHashMap<String,Integer>();
    var projected=new ArrayList<Map<String,Object>>();
    if(report.get("holdings") instanceof List<?> original)for(Object row:original){
      if(!(row instanceof Map<?,?> m))continue;
      var h=new LinkedHashMap<String,Object>();
      m.forEach((key,value)->{if(key instanceof String k)h.put(k,value);});
      var decision=holding(json.valueToTree(h),today,coverage);
      h.put("investment_analysis",decision);
      counts.merge((String)decision.get("action"),1,Integer::sum);
      projected.add(h);
    }
    out.put("holdings",projected);
    var steps=new ArrayList<String>();
    if(counts.getOrDefault("REVIEW_REDUCTION",0)>0||counts.getOrDefault("REASSESS_THESIS",0)>0)
      steps.add("First revisit weakened holding theses before committing new capital.");
    if(counts.getOrDefault("REBALANCE_REVIEW",0)>0||!root.path("portfolio_level_risk").path("attention").isEmpty())
      steps.add("Review concentration and overlap. Compare diversification through fresh contributions before selling.");
    if(!coverage||counts.getOrDefault("HOLD_PENDING_EVIDENCE",0)>0||counts.getOrDefault("PAUSE_ADDITIONS",0)>0)
      steps.add("Keep affected additions conditional on refreshed evidence; do not force deployment.");
    if(projected.isEmpty())steps.add("No holdings recorded; no personal allocation plan can be derived.");
    else steps.add("Compare new stock and fund research against existing exposure, cash needs and investment horizon before allocating.");
    var stress=new LinkedHashMap<String,Object>();
    if(coverage){
      double equity=0,funds=0,largest=0,hhi=0;boolean typesKnown=true;
      for(var h:holdings){
        double w=h.path("weight_percent").asDouble();largest=Math.max(largest,w);hhi+=Math.pow(w/100,2);
        if("EQUITY".equals(h.path("asset_type").asText()))equity+=w;
        else if("MUTUAL_FUND".equals(h.path("asset_type").asText()))funds+=w;
        else typesKnown=false;
      }
      if(typesKnown){
        stress.put("status","ILLUSTRATIVE_SHOCKS");stress.put("largest_position_percent",largest);stress.put("position_hhi",hhi);
        stress.put("scenarios",List.of(Map.of("case","BEAR","equity_shock_percent",-30,"fund_shock_percent",-20,"portfolio_change_percent",(-30*equity-20*funds)/100),
          Map.of("case","BASE","equity_shock_percent",0,"fund_shock_percent",0,"portfolio_change_percent",0),
          Map.of("case","BULL","equity_shock_percent",20,"fund_shock_percent",15,"portfolio_change_percent",(20*equity+15*funds)/100)));
      }
    }
    stress.putIfAbsent("status","AWAITING_COMPLETE_RECORDED_WEIGHTS");
    stress.put("notice","Hypothetical simultaneous shocks to recorded asset classes, not forecasts or probabilities. Fund look-through, correlations, taxes and liquidity are not modeled.");
    out.put("investment_analysis",Map.of("stress_test",stress,"methodology",VERSION,"scope","OWNER_LOCAL","status",projected.isEmpty()?"NO_HOLDINGS":"CONDITIONAL_PLAN",
      "holding_count",projected.size(),"recent_weight_coverage",coverage,"action_counts",counts,"next_steps",steps,"notice",NOTICE));
    return out;
  }
}
