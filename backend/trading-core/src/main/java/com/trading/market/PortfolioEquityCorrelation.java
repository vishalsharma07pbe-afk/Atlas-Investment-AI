package com.trading.market;

import java.math.BigDecimal;
import java.time.*;
import java.time.temporal.ChronoUnit;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;

/** Bounded historical correlation of adjusted direct-equity returns; never a forecast. */
final class PortfolioEquityCorrelation {
 private PortfolioEquityCorrelation(){}
 private static final int MAX_IDENTITIES=12, MIN_RETURNS=30;
 private record Identity(String isin,String symbol,long id,BigDecimal value){}
 record Interval(LocalDate start,LocalDate end){}
 record Pair(double correlation,int observations,LocalDate first,LocalDate last){}
 static Map<String,Object> collect(JdbcTemplate jdbc,List<Map<String,Object>> rows,LocalDate today){
  Map<String,Identity> byIsin=new TreeMap<>();
  for(var row:rows){
   if(!"EQUITY".equals(row.get("asset_type"))||!(row.get("isin") instanceof String isin)
      ||!isin.matches("IN[A-Z0-9]{10}")||!(row.get("instrument_id") instanceof Number id)
      ||!(row.get("market_value") instanceof BigDecimal value)||value.signum()<=0)continue;
   Identity next=new Identity(isin,String.valueOf(row.get("symbol")),id.longValue(),value);
   byIsin.merge(isin,next,(a,b)->new Identity(isin,a.id()<=b.id()?a.symbol():b.symbol(),
      Math.min(a.id(),b.id()),a.value().add(b.value())));
  }
  var selected=byIsin.values().stream().sorted(Comparator.comparing(Identity::value).reversed().thenComparing(Identity::isin)).limit(MAX_IDENTITIES).toList();
  Map<String,Map<Interval,Double>> series=new HashMap<>();
  if(selected.size()>=2)for(Identity item:selected){
   var history=jdbc.queryForList("""
     SELECT (candle_time AT TIME ZONE 'Asia/Kolkata')::date AS trade_date,
       close,source_id,adjustment_status FROM market_candles
     WHERE instrument_id=? AND timeframe='1d' AND is_complete
       AND quality_status IN ('VALIDATED_MANUAL','PROVIDER_VALIDATED')
       AND (candle_time AT TIME ZONE 'Asia/Kolkata')::date BETWEEN ?::date AND ?::date
     ORDER BY candle_time LIMIT 100
     """,item.id(),today.minusDays(90),today.minusDays(1));
   var returns=returns(history,today);
   if(!returns.isEmpty())series.put(item.isin(),returns);
  }
  List<Map<String,Object>> pairs=new ArrayList<>();
  int comparable=0;
  for(int i=0;i<selected.size();i++)for(int j=i+1;j<selected.size();j++){
   Identity a=selected.get(i),b=selected.get(j);
   Pair pair=compare(series.getOrDefault(a.isin(),Map.of()),series.getOrDefault(b.isin(),Map.of()),today);
   if(pair==null)continue;
   comparable++;
   pairs.add(Map.of("first_symbol",a.symbol(),"second_symbol",b.symbol(),"first_isin",a.isin(),"second_isin",b.isin(),
    "correlation",Math.round(pair.correlation()*10000d)/10000d,"observations",pair.observations(),
    "first_date",pair.first().toString(),"last_date",pair.last().toString(),"high_positive_correlation",pair.correlation()>=0.8));
  }
  pairs.sort(Comparator.<Map<String,Object>>comparingDouble(p->((Number)p.get("correlation")).doubleValue()).reversed()
   .thenComparing(p->(String)p.get("first_isin")).thenComparing(p->(String)p.get("second_isin")));
  int attempted=selected.size()*(selected.size()-1)/2;
  Map<String,Object> out=new LinkedHashMap<>();
  out.put("status",comparable==0?"UNAVAILABLE":comparable<attempted||selected.size()<byIsin.size()?"PARTIAL":"AVAILABLE");
  out.put("resolved_priced_equities",byIsin.size());out.put("selected_equities",selected.size());out.put("eligible_series",series.size());
  out.put("comparable_pairs",comparable);out.put("attempted_pairs",attempted);
  out.put("high_positive_pair_count",pairs.stream().filter(p->Boolean.TRUE.equals(p.get("high_positive_correlation"))).count());
  out.put("pairs",pairs);
  out.put("notice","Pearson correlation of matched consecutive observed return intervals from validated adjusted daily closes over the last 90 calendar days. At least 30 matched intervals, recent overlap and a single known source per series required. Up to 12 largest resolved priced direct equities. No fund look-through, future correlation or optimal allocation.");
  return out;
 }
 static Map<Interval,Double> returns(List<Map<String,Object>> rows,LocalDate today){
  if(rows.size()<MIN_RETURNS+1)return Map.of();
  NavigableMap<LocalDate,Double> prices=new TreeMap<>();Long source=null;
  for(var row:rows){
   Object date=row.get("trade_date");
   LocalDate day=date instanceof java.sql.Date d?d.toLocalDate():date instanceof LocalDate d?d:null;
   if(day==null||day.isBefore(today.minusDays(90))||!day.isBefore(today)
      ||!"ADJUSTED".equals(row.get("adjustment_status"))||!(row.get("source_id") instanceof Number s)
      ||!(row.get("close") instanceof Number n))return Map.of();
   double value=n.doubleValue();
   if(!Double.isFinite(value)||value<=0||prices.putIfAbsent(day,value)!=null)return Map.of();
   if(source==null)source=s.longValue();else if(source!=s.longValue())return Map.of();
  }
  if(prices.lastKey().isBefore(today.minusDays(5)))return Map.of();
  Map<Interval,Double> out=new HashMap<>();LocalDate prior=null;double priorPrice=0;
  for(var entry:prices.entrySet()){
   LocalDate day=entry.getKey();double price=entry.getValue();
   if(prior!=null&&ChronoUnit.DAYS.between(prior,day)<=7){
    double ret=price/priorPrice-1;
    if(!Double.isFinite(ret))return Map.of();
    out.put(new Interval(prior,day),ret);
   }
   prior=day;priorPrice=price;
  }
  return out.size()>=MIN_RETURNS?out:Map.of();
 }
 static Pair compare(Map<Interval,Double> a,Map<Interval,Double> b,LocalDate today){
  var dates=a.keySet().stream().filter(b::containsKey).sorted(Comparator.comparing(Interval::end).thenComparing(Interval::start)).toList();
  int n=dates.size();
  if(n<MIN_RETURNS||dates.getLast().end().isBefore(today.minusDays(5)))return null;
  double x=0,y=0;
  for(var d:dates){x+=a.get(d);y+=b.get(d);}
  x/=n;y/=n;
  double xx=0,yy=0,xy=0;
  for(var d:dates){double dx=a.get(d)-x,dy=b.get(d)-y;xx+=dx*dx;yy+=dy*dy;xy+=dx*dy;}
  if(xx<=1e-16||yy<=1e-16)return null;
  double correlation=xy/Math.sqrt(xx*yy);
  if(!Double.isFinite(correlation))return null;
  return new Pair(Math.max(-1,Math.min(1,correlation)),n,dates.getFirst().start(),dates.getLast().end());
 }
}
