package com.trading.market;

import java.time.*;
import java.util.*;
import java.security.MessageDigest;
import java.nio.charset.StandardCharsets;
import java.util.HexFormat;
import static com.trading.market.IntradayResearchService.num;

/** Fixed-rule research cases on completed 15-minute bars; not executable orders. */
final class IntradayScenario {
 static final String VERSION="INTRADAY-RANGE-1";
 static final String NOTICE="Opening-range extension is a hypothetical price reference, not observed overhead resistance. Lower reference is prior session-to-date high, not a guaranteed stop. Four completed bars, illustrative costs and gap stress, no fill, forecast or validated confidence.";
 static final List<Integer> COSTS=List.of(15,30,60);
 static final int HOLD=4;
 static Instant start(LocalDate day){return day.atTime(9,15).atZone(MarketCalendarService.IST).toInstant();}
 static Instant end(LocalDate day){return day.atTime(15,30).atZone(MarketCalendarService.IST).toInstant();}
 static boolean regular(Map<String,Object> context,LocalDate day){
  return context!=null&&day.toString().equals(context.get("session_date"))&&start(day).equals(IntradayVenueEvidence.instant(context.get("open_at")))&&end(day).equals(IntradayVenueEvidence.instant(context.get("close_at")))&&
    Set.of("MARKET_HOURS","POST_MARKET","PRE_MARKET","BEFORE_PRE_MARKET").contains(String.valueOf(context.get("phase")));
 }
 static boolean valid(List<Map<String,Object>> bars,Instant first){
  if(bars.isEmpty()||bars.size()>25)return false;
  for(int i=0;i<bars.size();i++){
   var r=bars.get(i);
   double o=num(r,"open"),h=num(r,"high"),l=num(r,"low"),c=num(r,"close"),v=num(r,"volume");
   if(!first.plusSeconds(900L*i).equals(IntradayVenueEvidence.instant(r.get("candle_time")))||
      !Double.isFinite(o+h+l+c+v)||l<=0||o<l||c<l||h<Math.max(o,c)||v<=0||v!=Math.floor(v))return false;
  }
  return true;
 }
 static String hash(List<Map<String,Object>> rows){
  try{
   var md=MessageDigest.getInstance("SHA-256");
   for(var r:rows){
    var line=new StringBuilder(IntradayVenueEvidence.instant(r.get("candle_time")).toString());
    for(String k:List.of("open","high","low","close","volume"))line.append('|').append(Double.toHexString(num(r,k)));
    md.update((line+"\n").getBytes(StandardCharsets.UTF_8));
   }
   return HexFormat.of().formatHex(md.digest());
  }catch(java.security.NoSuchAlgorithmException ex){throw new IllegalStateException(ex);}
 }
 static double ceiling(double low,double high,double stress,int bps){
  double c=bps/10000d;
  return (high+2*low*(1-stress/100))*(1-c)/(3*(1+c));
 }
 static Map<String,Object> plan(Map<String,Object> finding,List<Map<String,Object>> prefix,Instant published){
  if(!"VOLUME_BREAKOUT_WATCH".equals(finding.get("pattern")))return null;
  var day=published.atZone(MarketCalendarService.IST).toLocalDate();
  Instant signal=IntradayVenueEvidence.instant(finding.get("bar_end"));
  if(signal==null||signal.isAfter(published)||Duration.between(signal,published).toSeconds()>1200||!valid(prefix,start(day))||
     !signal.equals(start(day).plusSeconds(900L*prefix.size())))return null;
  double close=num(finding,"close"),low=num(finding,"prior_session_high_so_far"),range=num(finding,"opening_range_high")-num(finding,"opening_range_low");
  double high=low+2*range,stress=Math.max(.5,num(finding,"mean_bar_range_percent"));
  if(!Double.isFinite(close+low+high+stress)||!(0<low&&low<close&&close<high&&stress<100))return null;
  // First whole bar strictly AFTER actual publication; no retroactive entry
  // into a partially observed candle, even if the signal bar was just closed.
  long offset=Duration.between(start(day),published).getSeconds();
  long index=offset/900+1;
  Instant entry=start(day).plusSeconds(index*900),expiry=entry.plusSeconds(HOLD*900L);
  if(expiry.isAfter(end(day)))return null;
  List<Map<String,Object>> costs=new ArrayList<>();
  for(int bps:COSTS){
   double cap=ceiling(low,high,stress,bps);
   Map<String,Object> c=new LinkedHashMap<>();
   c.put("cost_bps_per_side",bps);c.put("entry_ceiling",cap>low&&cap<high?cap:null);
   c.put("reference_meets_stressed_ratio",close<=cap&&cap>low&&cap<high);costs.add(c);
  }
  return Map.ofEntries(Map.entry("methodology",VERSION),Map.entry("status","ILLUSTRATIVE_RANGE_PROJECTION"),
    Map.entry("bar_end",signal.toString()),Map.entry("published_at",published.toString()),Map.entry("entry_bar_start",entry.toString()),
    Map.entry("expiry",expiry.toString()),Map.entry("prefix_count",prefix.size()),Map.entry("prefix_sha256",hash(prefix)),
    Map.entry("reference_close",close),Map.entry("lower_reference",low),Map.entry("upper_projection",high),Map.entry("stress_gap_percent",stress),
    Map.entry("entry_cases",costs),Map.entry("notice",NOTICE));
 }
 static Map<String,Object> outcome(Map<String,Object> p,List<Map<String,Object>> rows,LocalDate day){
  Instant first=start(day),entry=IntradayVenueEvidence.instant(p.get("entry_bar_start")),expiry=IntradayVenueEvidence.instant(p.get("expiry")),signal=IntradayVenueEvidence.instant(p.get("bar_end"));
  if(entry==null||expiry==null||signal==null||!entry.isAfter(signal.minusNanos(1))||!expiry.equals(entry.plusSeconds(900L*HOLD))||expiry.isAfter(end(day))||!valid(rows,first))return gap();
  int n=(int)Duration.between(first,signal).toSeconds()/900,i=(int)Duration.between(first,entry).toSeconds()/900;
  if(n<6||i<n||i+HOLD>rows.size()||!first.plusSeconds(900L*n).equals(signal)||!first.plusSeconds(900L*i).equals(entry)||
     !Objects.equals(p.get("prefix_sha256"),hash(rows.subList(0,n))))return gap();
  double low=num(p,"lower_reference"),high=num(p,"upper_projection"),stress=num(p,"stress_gap_percent");
  if(!Double.isFinite(low+high+stress)||!(0<low&&low<high&&stress>=.5&&stress<100))return gap();
  boolean touched=false;
  for(var r:rows.subList(n,i))if(num(r,"low")<=low||num(r,"high")>=high)touched=true;
  List<Map<String,Object>> cases=new ArrayList<>();
  for(int bps:COSTS){
   var c=touched?Map.<String,Object>of("status","NO_ENTRY_INTERVENING_TOUCH"):simulate(low,high,stress,rows.subList(i,i+HOLD),bps);
   var item=new LinkedHashMap<>(c);item.put("cost_bps_per_side",bps);cases.add(item);
  }
  return Map.of("status","OBSERVED_CASES","cases",cases,"notice",NOTICE);
 }
 static Map<String,Object> gap(){return Map.of("status","EVIDENCE_GAP","cases",List.of());}
 static double net(double entry,double exit,int bps){double c=bps/10000d;return 100*(exit*(1-c)/(entry*(1+c))-1);}
 static Map<String,Object> resolved(String state,double entry,double exit,int bps){return Map.of("status",state,"entry_open",entry,"exit_reference",exit,"net_change_percent",net(entry,exit,bps));}
 static Map<String,Object> simulate(double low,double high,double stress,List<Map<String,Object>> rows,int bps){
  double entry=num(rows.getFirst(),"open");
  if(entry<=low||entry>=high)return Map.of("status","NO_ENTRY_OUTSIDE_BRACKET");
  if(entry>ceiling(low,high,stress,bps))return Map.of("status","NO_ENTRY_STRESS_RATIO");
  for(var r:rows){
   double o=num(r,"open"),h=num(r,"high"),l=num(r,"low");
   if(o<=low)return resolved("LOWER_GAP",entry,o,bps);
   if(o>=high)return resolved("UPPER_GAP",entry,high,bps);
   if(l<=low&&h>=high)return Map.of("status","AMBIGUOUS_BOTH_BOUNDARIES","lower_case_net_percent",net(entry,low,bps),"upper_case_net_percent",net(entry,high,bps));
   if(l<=low)return resolved("LOWER_TOUCHED",entry,low,bps);
   if(h>=high)return resolved("UPPER_TOUCHED",entry,high,bps);
  }
  return resolved("EXPIRED_CLOSE",entry,num(rows.getLast(),"close"),bps);
 }
 static Map<String,Object> replay(List<Map<String,Object>> rows,LocalDate day){
  if(rows.size()!=25||!valid(rows,start(day)))return gap();
  // First qualifying geometry only; fixed hypothetical publication at signal
  // completion, same strict next-whole-bar delay as prospective observations.
  for(int n=6;n<=25-HOLD-1;n++){
   Instant signal=start(day).plusSeconds(n*900L);
   var prefix=rows.subList(0,n);
   var finding=IntradayResearchService.evaluate(prefix,signal);
   if(finding==null)continue;
   var p=plan(finding,prefix,signal);
   if(p!=null)return outcome(p,rows,day);
  }
  return Map.of("status","NO_SCENARIO","cases",List.of());
 }
}
