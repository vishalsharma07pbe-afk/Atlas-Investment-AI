package com.trading.market;

import java.time.*;
import java.util.*;

/** Public cached quote comparison only, never an executable venue choice. */
final class IntradayVenueEvidence {
 private IntradayVenueEvidence(){}
 static final String NOTICE="Same-company sampled current-session observations only. Preference requires same completed bar, paired fresh quotes, narrower spread and no lower activity proxy. No verified execution or exchange clearance.";
 static final Set<String> SPECIAL=Set.of("PCA","SME","RELIST","IPO","SUSPENDED_REPORTED");
 record Choice(Map<String,Object> row,Map<String,Object> context){}
 static boolean restricted(Map<String,Object> row){return SPECIAL.contains(String.valueOf(row.get("security_state")));}
 static Instant instant(Object value){
  if(value instanceof java.sql.Timestamp t)return t.toInstant();
  if(value instanceof OffsetDateTime t)return t.toInstant();
  if(value instanceof Instant t)return t;
  if(value instanceof String s)try{return Instant.parse(s);}catch(DateTimeException ex){return null;}
  return null;
 }
 static Map<String,Object> quote(Map<String,Object> source,Instant now){
  Instant observed=instant(source.get("quote_observed_at")),response=instant(source.get("quote_response_at"));
  if(observed==null||response==null||observed.isBefore(now.minusSeconds(900))||observed.isAfter(response)||response.isAfter(now)
      ||!observed.atZone(MarketCalendarService.IST).toLocalDate().equals(now.atZone(MarketCalendarService.IST).toLocalDate()))return null;
  double price=IntradayResearchService.num(source,"quote_price"),spread=IntradayResearchService.num(source,"quote_spread_percent"),
      turnover=IntradayResearchService.num(source,"quote_turnover");
  if(!Double.isFinite(price)||price<=0||!Double.isFinite(spread)||spread<0||!Double.isFinite(turnover)||turnover<=0)return null;
  return Map.of("observed_at",observed.toString(),"response_at",response.toString(),"price",price,
       "spread_percent",spread,"turnover_proxy_cr",turnover/1e7);
 }
 static Map<String,Object> fresh(Map<String,Object> row,Instant now){
  if(!(row.get("venue_quote") instanceof Map<?,?> q))return null;
  Map<String,Object> input=new HashMap<>();
  input.put("quote_observed_at",q.get("observed_at"));input.put("quote_response_at",q.get("response_at"));
  input.put("quote_price",q.get("price"));input.put("quote_spread_percent",q.get("spread_percent"));
  if(q.get("turnover_proxy_cr") instanceof Number n)input.put("quote_turnover",n.doubleValue()*1e7);
  return quote(input,now);
 }
 static List<String> restrictionFindings(List<Map<String,Object>> rows){
  return rows.stream().filter(IntradayVenueEvidence::restricted)
    .map(r->"REPORTED_"+r.get("security_state")+"_AT_"+r.get("exchange")).distinct().sorted().toList();
 }
 static Choice choose(List<Map<String,Object>> ranked,List<Map<String,Object>> observed,Instant now){
  if(ranked.isEmpty())return null;
  Map<String,Map<String,Object>> venues=new TreeMap<>();
  for(var row:observed){
   String exchange=String.valueOf(row.get("exchange"));
   if(!Set.of("NSE","BSE").contains(exchange)||!Objects.equals(row.get("isin"),ranked.getFirst().get("isin")))return null;
   var previous=venues.putIfAbsent(exchange,row);
   if(previous!=null&&!previous.equals(row))return null;
  }
  var valid=ranked.stream().filter(r->!restricted(r)
    &&(!venues.containsKey(String.valueOf(r.get("exchange")))||
        (Objects.equals(venues.get(String.valueOf(r.get("exchange"))).get("id"),r.get("id"))
          &&!restricted(venues.get(String.valueOf(r.get("exchange"))))))).toList();
  if(valid.isEmpty())return null;
  if(valid.stream().map(r->r.get("exchange")).distinct().count()!=valid.size())return null;
  var chosen=valid.getFirst();
  String preference=null,status="SCREEN_REPRESENTATIVE_ONLY";
  if(valid.size()==2&&Objects.equals(valid.get(0).get("bar_end"),valid.get(1).get("bar_end"))
      &&valid.getFirst().get("bar_end")!=null){
   var first=valid.get(0);var second=valid.get(1);
   var x=fresh(first,now);var y=fresh(second,now);
   if(x!=null&&y!=null&&Math.abs(Duration.between(instant(x.get("observed_at")),instant(y.get("observed_at"))).toMillis())<=60000){
    status="PAIRED_QUOTE_NO_CLEAR_PREFERENCE";
    double xs=IntradayResearchService.num(x,"spread_percent"),ys=IntradayResearchService.num(y,"spread_percent");
    double xt=IntradayResearchService.num(x,"turnover_proxy_cr"),yt=IntradayResearchService.num(y,"turnover_proxy_cr");
    if(xs<ys&&xt>=yt){chosen=first;preference=String.valueOf(first.get("exchange"));}
    else if(ys<xs&&yt>=xt){chosen=second;preference=String.valueOf(second.get("exchange"));}
    if(preference!=null)status="PAIRED_QUOTE_LIQUIDITY_PREFERENCE";
   }
  }
  List<Map<String,Object>> detail=new ArrayList<>();
  for(var row:venues.values()){
   Map<String,Object> item=new LinkedHashMap<>();
   for(String key:List.of("exchange","symbol","bar_end","close","pattern","security_state"))item.put(key,row.get(key));
   item.put("quote",fresh(row,now));detail.add(item);
  }
  Map<String,Object> context=new LinkedHashMap<>();
  context.put("methodology","COMPANY-VENUE-INTRADAY-1");context.put("status",status);context.put("preferred_exchange",preference);
  context.put("representative_exchange",chosen.get("exchange"));context.put("observed_venues",List.copyOf(venues.keySet()));
  context.put("venue_observations",detail);context.put("review_findings",restrictionFindings(observed));
  context.put("execution_verified",false);context.put("notice",NOTICE);
  return new Choice(chosen,context);
 }
}
