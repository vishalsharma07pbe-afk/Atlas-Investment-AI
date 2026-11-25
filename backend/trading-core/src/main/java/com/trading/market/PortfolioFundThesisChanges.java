package com.trading.market;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.time.*;
import java.util.*;

/** Local comparison of dated secondary disclosures, never a forecast or trade instruction. */
final class PortfolioFundThesisChanges {
  private PortfolioFundThesisChanges(){}
  private static final String SOURCE="TIGZIG_AMFI_DERIVED";
  private static final List<String> RISKS=List.of("LOW","LOW_TO_MODERATE","MODERATE","MODERATELY_HIGH","HIGH","VERY_HIGH");
  private static final Map<String,String> DATES=Map.of("TER","ter_date","RISKOMETER","aum_date","BENCHMARK","aum_date",
    "MANAGERS","document_date","EXIT_LOAD","document_date");
  record Signal(String metric,String date,String value){}
  record Change(String metric,String previousDate,String currentDate,String previousValue,String currentValue,
      String attention,String observedAt){}

  private static LocalDate date(String value){
    try{return LocalDate.parse(value);}catch(RuntimeException ex){return null;}
  }
  private static String holdingKey(JsonNode h){
    String code=h.path("exact_scheme_code").asText();
    return "MUTUAL_FUND".equals(h.path("asset_type").asText())&&h.path("id").isIntegralNumber()&&
      code.matches("[1-9][0-9]{5,8}")?h.path("id").asText()+":"+code:null;
  }
  private static String evidenceKey(JsonNode h){
    var evidence=h.path("fund_thesis_evidence");var d=evidence.path("disclosure");
    String code=d.path("scheme_code").asText(),isin=d.path("isin").asText(),plan=d.path("plan").asText();
    if(!"SECONDARY_REPORTED_EVIDENCE".equals(evidence.path("status").asText())||
      !SOURCE.equals(d.path("source").asText())||!code.equals(h.path("exact_scheme_code").asText())||
      !isin.matches("IN[A-Z0-9]{10}")||!Set.of("DIRECT","REGULAR").contains(plan))return null;
    return code+":"+isin+":"+plan+":"+SOURCE;
  }
  private static String text(JsonNode d,String field,int max){
    var node=d.path(field);if(!node.isTextual())return null;
    String value=node.asText().strip().replaceAll("\\s+"," ");
    return value.isBlank()||value.length()>max?null:value;
  }
  private static List<Signal> signals(JsonNode h,Instant now){
    if(evidenceKey(h)==null)return List.of();
    var d=h.path("fund_thesis_evidence").path("disclosure");
    LocalDate today=now.atZone(MarketCalendarService.IST).toLocalDate();
    try{
      Instant collected=OffsetDateTime.parse(d.path("collected_at").asText()).toInstant();
      if(collected.isAfter(now)||collected.isBefore(now.minus(Duration.ofDays(3))))return List.of();
    }catch(RuntimeException ex){return List.of();}
    Set<String> conflicts=new HashSet<>();d.path("conflicts").forEach(x->conflicts.add(x.asText()));
    Map<String,String> values=new TreeMap<>();
    var ter=d.path("ter_percent");
    if(ter.isNumber()&&Double.isFinite(ter.asDouble())&&ter.asDouble()>=0&&ter.asDouble()<=100)
      values.put("TER",ter.decimalValue().stripTrailingZeros().toPlainString());
    String risk=text(d,"riskometer",40);
    if(risk!=null&&RISKS.contains(risk)&&!conflicts.contains("RISKOMETER_CONFLICT"))values.put("RISKOMETER",risk);
    if(!conflicts.contains("BENCHMARK_CONFLICT"))values.put("BENCHMARK",text(d,"benchmark",300));
    values.put("MANAGERS",text(d,"fund_managers",1000));values.put("EXIT_LOAD",text(d,"exit_load",2000));
    List<Signal> out=new ArrayList<>();
    values.forEach((metric,value)->{
      LocalDate day=date(d.path(DATES.get(metric)).asText());
      int age="TER".equals(metric)?90:Set.of("RISKOMETER","BENCHMARK").contains(metric)?14:365;
      if(value!=null&&day!=null&&!day.isAfter(today)&&!day.isBefore(today.minusDays(age)))
        out.add(new Signal(metric,day.toString(),value));
    });
    return out;
  }
  private static boolean equal(Signal a,Signal b){
    return "TER".equals(a.metric())?new BigDecimal(a.value()).compareTo(new BigDecimal(b.value()))==0:a.value().equalsIgnoreCase(b.value());
  }
  private static String attention(Signal a,Signal b){
    if("TER".equals(a.metric()))return new BigDecimal(b.value()).compareTo(new BigDecimal(a.value()))>0?"REVIEW":"OBSERVE";
    if("RISKOMETER".equals(a.metric()))return RISKS.indexOf(b.value())>RISKS.indexOf(a.value())?"REVIEW":"OBSERVE";
    return "REVIEW";
  }

  @SuppressWarnings("unchecked")
  static Map<String,Object> attach(Map<String,Object> report,JsonNode prior,ObjectMapper json,Instant now){
    if(!(report.get("holdings") instanceof List<?> raw))return report;
    Map<String,JsonNode> old=new HashMap<>();
    for(var h:prior.path("holdings")){String key=holdingKey(h);if(key!=null)old.put(key,h);}
    List<Map<String,Object>> holdings=new ArrayList<>();int changed=0,attentionCount=0;
    for(Object item:raw){
      if(!(item instanceof Map<?,?> map))continue;
      var h=new LinkedHashMap<String,Object>((Map<String,Object>)map);
      if(!"MUTUAL_FUND".equals(h.get("asset_type"))){holdings.add(h);continue;}
      JsonNode current=json.valueToTree(h);
      String key=holdingKey(current),identity=evidenceKey(current);
      JsonNode previous=key==null?json.createObjectNode():old.getOrDefault(key,json.createObjectNode());
      String previousIdentity=previous.path("fund_monitor_identity").asText();
      boolean same=key!=null&&!previousIdentity.isBlank()&&(identity==null||identity.equals(previousIdentity));
      Map<String,Signal> baseline=new TreeMap<>();
      Map<String,Change> recent=new TreeMap<>();
      if(same){
        for(var row:previous.path("fund_monitor_baseline"))try{
          Signal s=json.treeToValue(row,Signal.class);
          if(DATES.containsKey(s.metric())&&date(s.date())!=null&&s.value()!=null)baseline.put(s.metric(),s);
        }catch(Exception ignored){}
        for(var row:previous.path("fund_recent_changes"))try{
          Change c=json.treeToValue(row,Change.class);
          Instant at=Instant.parse(c.observedAt());
          if(DATES.containsKey(c.metric())&&!at.isAfter(now)&&!at.isBefore(now.minus(Duration.ofDays(7))))recent.put(c.metric(),c);
        }catch(Exception ignored){}
      }
      List<Signal> fresh=signals(current,now);
      for(var s:fresh){
        Signal before=baseline.get(s.metric());
        if(before==null){baseline.put(s.metric(),s);continue;}
        if(!date(s.date()).isAfter(date(before.date())))continue; // no same-date correction or rollback signal
        try{
          if(!equal(before,s))recent.put(s.metric(),new Change(s.metric(),before.date(),s.date(),before.value(),s.value(),attention(before,s),now.toString()));
          baseline.put(s.metric(),s);
        }catch(RuntimeException ex){baseline.put(s.metric(),s);recent.remove(s.metric());}
      }
      List<Change> visible=new ArrayList<>();
      for(var s:fresh){
        Change c=recent.get(s.metric());
        Signal saved=baseline.get(s.metric());
        if(c!=null&&saved!=null&&s.date().equals(saved.date())&&s.value().equals(saved.value())&&
            s.value().equals(c.currentValue())&&!date(s.date()).isBefore(date(c.currentDate())))visible.add(c);
      }
      if(!visible.isEmpty())changed++;
      if(visible.stream().anyMatch(c->"REVIEW".equals(c.attention())))attentionCount++;
      h.put("fund_monitor_identity",identity!=null?identity:same?previousIdentity:null);
      h.put("fund_monitor_baseline",List.copyOf(baseline.values()));
      h.put("fund_recent_changes",List.copyOf(recent.values()));
      h.put("fund_thesis_changes",visible);
      h.put("fund_monitor_status",fresh.isEmpty()?"NO_CURRENT_DATED_DISCLOSURES":visible.isEmpty()?"NO_RECENT_DISCLOSURE_CHANGE":"RECENT_DISCLOSURE_CHANGE");
      holdings.add(h);
    }
    var result=new LinkedHashMap<>(report);result.put("holdings",holdings);
    result.put("fund_thesis_changed_count",changed);result.put("fund_thesis_attention_count",attentionCount);
    result.put("fund_monitor_notice","Dated secondary disclosure changes observed in the last seven days. Missing evidence does not imply improvement; reported changes require official verification.");
    return result;
  }
}
