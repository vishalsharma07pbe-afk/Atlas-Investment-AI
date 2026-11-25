package com.trading.market;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.time.*;
import java.time.temporal.TemporalAdjusters;
import java.util.*;

/** Owner-scoped lifecycle of reported shareholding percentages, not transactions. */
final class PortfolioOwnershipChanges {
  private PortfolioOwnershipChanges(){}
  private static final Set<String> CATEGORIES=Set.of("promoters","fii","other_dii","mutual_funds","retail_and_other");
  private static final BigDecimal ONE=BigDecimal.ONE;
  record Quarter(String date,Map<String,BigDecimal> weights){}
  record Change(String category,String previousDate,String currentDate,BigDecimal previousPercent,
      BigDecimal currentPercent,BigDecimal changePp,String attention,String observedAt){}
  private static LocalDate date(String value){
    try{
      var d=LocalDate.parse(value);
      return d.getMonthValue()%3==0&&d.equals(d.with(TemporalAdjusters.lastDayOfMonth()))?d:null;
    }catch(RuntimeException ex){return null;}
  }
  private static String identity(JsonNode h){
    String isin=h.path("isin").asText(),exchange=h.path("exchange").asText();
    return "EQUITY".equals(h.path("asset_type").asText())&&h.path("id").isIntegralNumber()&&
      isin.matches("IN[A-Z0-9]{10}")&&Set.of("NSE","BSE").contains(exchange)?
      h.path("id").asText()+":"+exchange+":"+isin:null;
  }
  private static boolean validWeights(Map<String,BigDecimal> weights){
    if(weights==null||!weights.keySet().equals(CATEGORIES))return false;
    BigDecimal total=BigDecimal.ZERO;
    for(BigDecimal value:weights.values()){
      if(value==null||value.signum()<0||value.compareTo(BigDecimal.valueOf(100))>0)return false;
      total=total.add(value);
    }
    return total.compareTo(new BigDecimal("99.5"))>=0&&total.compareTo(new BigDecimal("100.5"))<=0;
  }
  private static boolean same(Quarter a,Quarter b){
    return a!=null&&b!=null&&a.date().equals(b.date())&&validWeights(a.weights())&&validWeights(b.weights())&&
      CATEGORIES.stream().allMatch(k->a.weights().get(k).compareTo(b.weights().get(k))==0);
  }
  private static Quarter quarter(JsonNode ownership,String dateField,String weightField){
    String day=ownership.path(dateField).asText();
    if(date(day)==null)return null;
    Map<String,BigDecimal> weights=new TreeMap<>();
    for(var row:ownership.path("categories")){
      String key=row.path("category").asText();var value=row.path(weightField);
      if(!CATEGORIES.contains(key)||!value.isNumber()||!Double.isFinite(value.asDouble())||
          weights.putIfAbsent(key,value.decimalValue())!=null)return null;
    }
    return validWeights(weights)?new Quarter(day,weights):null;
  }
  private static Quarter[] fresh(JsonNode holding,Instant now){
    if(identity(holding)==null)return null;
    var company=holding.path("thesis_evidence").path("company_evidence");
    if(!holding.path("isin").asText().equals(company.path("isin").asText()))return null;
    try{
      Instant retrieved=Instant.parse(company.path("retrieved_at").asText());
      if(retrieved.isAfter(now)||retrieved.isBefore(now.minus(Duration.ofHours(24))))return null;
    }catch(RuntimeException ex){return null;}
    var source=company.path("sections").path("shareholding").path("source");
    if(!"UPSTOX".equals(source.path("provider").asText()))return null;
    var ownership=company.path("ownership_research");
    String status=ownership.path("status").asText();
    if(!Set.of("COMPARABLE_QUARTERS","LATEST_QUARTER_ONLY").contains(status))return null;
    Quarter latest=quarter(ownership,"latest_period","latest_percent");
    if(latest==null)return null;
    LocalDate today=now.atZone(MarketCalendarService.IST).toLocalDate(),end=date(latest.date());
    if(end.isAfter(today)||end.isBefore(today.minusDays(150)))return null;
    Quarter prior="COMPARABLE_QUARTERS".equals(status)?quarter(ownership,"previous_period","previous_percent"):null;
    if(prior!=null&&!date(prior.date()).equals(end.minusMonths(3).with(TemporalAdjusters.lastDayOfMonth())))prior=null;
    return new Quarter[]{latest,prior};
  }

  @SuppressWarnings("unchecked")
  static Map<String,Object> attach(Map<String,Object> report,JsonNode prior,ObjectMapper json,Instant now){
    if(!(report.get("holdings") instanceof List<?> raw))return report;
    Map<String,JsonNode> old=new HashMap<>();
    for(var row:prior.path("holdings")){String key=identity(row);if(key!=null)old.put(key,row);}
    List<Map<String,Object>> holdings=new ArrayList<>();int changed=0,attention=0;
    for(Object item:raw){
      if(!(item instanceof Map<?,?> map))continue;
      var h=new LinkedHashMap<String,Object>((Map<String,Object>)map);
      if(!"EQUITY".equals(h.get("asset_type"))){holdings.add(h);continue;}
      JsonNode current=json.valueToTree(h);String key=identity(current);
      JsonNode previous=key==null?json.createObjectNode():old.getOrDefault(key,json.createObjectNode());
      Quarter baseline=null;
      try{
        Quarter saved=json.treeToValue(previous.path("ownership_monitor_baseline"),Quarter.class);
        if(saved!=null&&date(saved.date())!=null&&validWeights(saved.weights()))baseline=saved;
      }catch(Exception ignored){/* No trustworthy prior baseline. */}
      List<Change> recent=new ArrayList<>();
      for(var row:previous.path("ownership_recent_changes"))try{
        Change c=json.treeToValue(row,Change.class);
        Instant at=Instant.parse(c.observedAt());
        if(CATEGORIES.contains(c.category())&&!at.isAfter(now)&&!at.isBefore(now.minus(Duration.ofDays(7))))recent.add(c);
      }catch(Exception ignored){}
      Quarter[] evidence=fresh(current,now);
      Quarter latest=evidence==null?null:evidence[0],previousQuarter=evidence==null?null:evidence[1];
      String status="NO_CURRENT_COMPLETE_OWNERSHIP";
      if(latest!=null){
        status="BASELINE_RECORDED";
        if(baseline!=null){
          int comparison=date(latest.date()).compareTo(date(baseline.date()));
          status=comparison<0?"OLDER_QUARTER_IGNORED":comparison==0?
            (same(latest,baseline)?"NO_NEW_QUARTER":"SAME_QUARTER_REVISION_UNVERIFIED"):"NEW_BASELINE_WITHOUT_MATCHED_PRIOR";
          if(comparison>0){
            recent.clear();
            if(same(previousQuarter,baseline)){
              status="NEW_MATCHED_QUARTER";
              for(String category:new TreeSet<>(CATEGORIES)){
                BigDecimal before=baseline.weights().get(category),after=latest.weights().get(category),delta=after.subtract(before);
                if(delta.abs().compareTo(ONE)>=0)
                  recent.add(new Change(category,baseline.date(),latest.date(),before,after,delta,
                    delta.compareTo(ONE.negate())<=0&&!"retail_and_other".equals(category)?"REVIEW":"OBSERVE",now.toString()));
              }
            }
            baseline=latest;
          }
        }else baseline=latest;
      }
      List<Change> visible=new ArrayList<>();
      if(same(latest,baseline)&&previousQuarter!=null){
        for(var c:recent)if(c.currentDate().equals(latest.date())&&c.previousDate().equals(previousQuarter.date())&&
            c.currentPercent().compareTo(latest.weights().get(c.category()))==0&&
            c.previousPercent().compareTo(previousQuarter.weights().get(c.category()))==0)visible.add(c);
      }
      if(!visible.isEmpty())changed++;
      if(visible.stream().anyMatch(c->"REVIEW".equals(c.attention())))attention++;
      h.put("ownership_monitor_baseline",baseline);h.put("ownership_recent_changes",recent);
      h.put("ownership_changes",visible);h.put("ownership_monitor_status",status);
      holdings.add(h);
    }
    var result=new LinkedHashMap<>(report);result.put("holdings",holdings);
    result.put("ownership_changed_count",changed);result.put("ownership_attention_count",attention);
    result.put("ownership_monitor_notice","New matched quarterly ownership changes of at least one percentage point, observed in the past seven days; not evidence of trades or pledges.");
    return result;
  }
}
