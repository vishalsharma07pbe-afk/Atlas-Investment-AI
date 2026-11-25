package com.trading.market;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.*;
import java.time.Instant;

/** Compare dated financial direction on the same exact held identity. No model calls. */
final class PortfolioThesisChanges {
  private PortfolioThesisChanges(){}
  private static final Set<String> METRICS=Set.of("REVENUE","NET_PROFIT","OPERATING_PROFIT","OPERATING_CASH_FLOW");
  record Signal(String metric,int year,String period,String unit,String direction){}

  static List<Signal> signals(JsonNode holding){
    if(!"EQUITY".equals(holding.path("asset_type").asText())||
        !holding.path("isin").asText().matches("IN[A-Z0-9]{10}"))return List.of();
    Map<String,List<Signal>> byMetric=new TreeMap<>();
    for(var row:holding.path("thesis_evidence").path("company_evidence").path("financial_trends").path("items")){
      String metric=row.path("metric").asText(),period=row.path("latest_period").asText(),unit=row.path("unit").asText();
      int year=row.path("latest_year").asInt(),previous=row.path("previous_year").asInt();
      var old=row.path("previous_value");var latest=row.path("latest_value");
      if(!METRICS.contains(metric)||year<2001||year-previous!=1||period.isBlank()||unit.isBlank()||
          row.path("latest_period_may_be_stale").asBoolean(true)||!old.isNumber()||!latest.isNumber()||
          !Double.isFinite(old.asDouble())||!Double.isFinite(latest.asDouble()))continue;
      String direction=latest.asDouble()<0?"NEGATIVE":latest.asDouble()<old.asDouble()?"DECLINING":
        latest.asDouble()>old.asDouble()?"IMPROVING":"UNCHANGED";
      byMetric.computeIfAbsent(metric,k->new ArrayList<>()).add(new Signal(metric,year,period,unit,direction));
    }
    return byMetric.values().stream().filter(v->v.size()==1).map(List::getFirst).toList();
  }

  @SuppressWarnings("unchecked")
  static Map<String,Object> attach(Map<String,Object> report,JsonNode prior,ObjectMapper json,Instant now){
    if(!(report.get("holdings") instanceof List<?> raw))return report;
    Map<String,JsonNode> previous=new HashMap<>();
    for(var h:prior.path("holdings")){String key=identity(h);if(key!=null)previous.put(key,h);}
    List<Map<String,Object>> holdings=new ArrayList<>();int changed=0;
    for(Object item:raw){
      if(!(item instanceof Map<?,?> map))continue;
      var h=new LinkedHashMap<String,Object>((Map<String,Object>)map);
      JsonNode current=json.valueToTree(h);String key=identity(current);
      var old=key==null?json.createObjectNode():previous.getOrDefault(key,json.createObjectNode());
      Map<String,Signal> baseline=new TreeMap<>();
      for(var s:old.path("thesis_direction_baseline")){
        try{Signal value=json.treeToValue(s,Signal.class);if(METRICS.contains(value.metric()))baseline.put(value.metric(),value);}
        catch(Exception ignored){/* Corrupt older baseline is not evidence. */}
      }
      List<Signal> fresh=signals(current);
      List<Map<String,String>> changes=new ArrayList<>();
      for(var s:fresh){
        Signal before=baseline.get(s.metric());
        if(before!=null&&s.year()==before.year()+1&&s.unit().equals(before.unit())&&
            !s.period().equals(before.period())&&!s.direction().equals(before.direction())){
          changes.add(Map.of("metric",s.metric(),"previous_period",before.period(),"current_period",s.period(),
            "previous_direction",before.direction(),"current_direction",s.direction(),"observed_at",now.toString()));
        }
        if(before==null||s.year()>before.year()||(s.year()==before.year()&&s.period().equals(before.period())&&s.unit().equals(before.unit())))
          baseline.put(s.metric(),s);
      }
      boolean newlyChanged=!changes.isEmpty();
      // Retain recent observed changes across routine refreshes, but do not
      // display them as current when the corresponding evidence disappears.
      for(var previousChange:old.path("thesis_recent_changes")){
        String metric=previousChange.path("metric").asText();
        if(changes.stream().anyMatch(x->metric.equals(x.get("metric"))))continue;
        try{
          Instant at=Instant.parse(previousChange.path("observed_at").asText());
          if(at.isAfter(now)||at.isBefore(now.minus(java.time.Duration.ofDays(7))))continue;
          Signal currentSignal=baseline.get(metric);
          if(currentSignal==null||!currentSignal.period().equals(previousChange.path("current_period").asText())||
              !currentSignal.direction().equals(previousChange.path("current_direction").asText()))continue;
          Map<String,String> retained=new LinkedHashMap<>();
          for(String field:List.of("metric","previous_period","current_period","previous_direction","current_direction","observed_at"))
            retained.put(field,previousChange.path(field).asText());
          changes.add(retained);
        }catch(RuntimeException ignored){/* Invalid stored timestamp. */}
      }
      h.put("thesis_recent_changes",changes);
      var visible=changes.stream().filter(change->fresh.stream().anyMatch(s->s.metric().equals(change.get("metric"))&&
        s.period().equals(change.get("current_period"))&&s.direction().equals(change.get("current_direction")))).toList();
      if(!visible.isEmpty())changed++;
      h.put("thesis_direction_baseline",List.copyOf(baseline.values()));
      h.put("thesis_changes",visible);
      h.put("thesis_monitor_status",fresh.isEmpty()?"NO_CURRENT_DATED_TRENDS":visible.isEmpty()?"NO_NEW_DIRECTION_CHANGE":newlyChanged?"NEW_REPORTED_DIRECTION_CHANGE":"RECENT_REPORTED_DIRECTION_CHANGE");
      holdings.add(h);
    }
    var result=new LinkedHashMap<>(report);result.put("holdings",holdings);
    result.put("thesis_changed_count",changed);result.put("thesis_monitor_notice","Consecutive annual reported direction changes observed in the last seven days only; missing evidence never implies recovery. No investment verdict.");
    return result;
  }
  private static String identity(JsonNode h){
    String isin=h.path("isin").asText(),exchange=h.path("exchange").asText();
    return "EQUITY".equals(h.path("asset_type").asText())&&isin.matches("IN[A-Z0-9]{10}")&&
      Set.of("NSE","BSE").contains(exchange)&&h.path("id").isIntegralNumber()?h.path("id").asText()+":"+exchange+":"+isin:null;
  }
}
