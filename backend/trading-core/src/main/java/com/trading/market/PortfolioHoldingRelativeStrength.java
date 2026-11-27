package com.trading.market;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;

/** Local, bounded, exact-session price-relative observations, independent of watch selection. */
final class PortfolioHoldingRelativeStrength {
 private PortfolioHoldingRelativeStrength(){}
 static final String NOTICE="NSE adjusted provider-validated equity closes versus Nifty 50 price-index closes on the same stored regular sessions; not total return, sector benchmark, forecast alpha or execution advice.";
 record Point(LocalDate date,BigDecimal close,String source,boolean eligible){}
 private static LocalDate day(Object v){return v instanceof java.sql.Date d?d.toLocalDate():v instanceof LocalDate d?d:null;}
 static Map<String,Object> collect(JdbcTemplate jdbc,List<Map<String,Object>> rows,LocalDate today){
  Map<String,Object> out=new HashMap<>();
  if(rows.stream().noneMatch(r->"EQUITY".equals(r.get("asset_type"))&&"NSE".equals(r.get("exchange"))))return out;
  var calendar=new TreeMap<LocalDate,String>();
  Object raw=new MarketCalendarService(jdbc).historicalContext("NSE",today).get("days");
  if(!(raw instanceof List<?> days))return out;
  for(Object entry:days){
   if(!(entry instanceof Map<?,?> m)||!(m.get("trade_date") instanceof String date)||!(m.get("state") instanceof String state))return out;
   if(calendar.putIfAbsent(LocalDate.parse(date),state)!=null)return out;
  }
  var benchmark=PortfolioBenchmarkEvidence.points(jdbc,today.minusDays(1),today,BenchmarkHistoryService.KEY,470).stream()
    .map(b->new Point(b.date(),b.close(),b.source(),b.eligible())).toList();
  Map<String,List<Point>> sectors=new LinkedHashMap<>();
  for(String key:BenchmarkHistoryService.SECTOR_KEYS){
   var points=PortfolioBenchmarkEvidence.points(jdbc,today.minusDays(1),today,key,470).stream()
     .map(b->new Point(b.date(),b.close(),b.source(),b.eligible())).toList();
   if(!points.isEmpty())sectors.put(key,points);
  }
  if(benchmark.isEmpty()&&sectors.isEmpty())return out;
  Set<Long> seen=new HashSet<>();
  for(var row:rows){
   if(!"EQUITY".equals(row.get("asset_type"))||!"NSE".equals(row.get("exchange"))
     ||!(row.get("isin") instanceof String isin)||!isin.matches("INE[A-Z0-9]{9}")
     ||!(row.get("instrument_id") instanceof Number id)||id.longValue()<=0)continue;
   if(seen.contains(id.longValue()))continue;
   if(seen.size()>=30)break;
   seen.add(id.longValue());
   var history=jdbc.queryForList("""
     SELECT (c.candle_time AT TIME ZONE 'Asia/Kolkata')::date AS trade_date,c.close,ds.source_code,
       (c.is_complete AND c.quality_status='PROVIDER_VALIDATED' AND c.adjustment_status='ADJUSTED'
         AND ds.enabled AND c.candle_time<=now()
         AND EXISTS(SELECT 1 FROM market_sessions ms WHERE ms.exchange_id=i.exchange_id
           AND ms.session_date=(c.candle_time AT TIME ZONE 'Asia/Kolkata')::date
           AND ms.session_type='REGULAR' AND ms.is_trading_day AND ms.close_time=c.candle_time)) AS eligible
     FROM market_candles c JOIN instruments i ON i.id=c.instrument_id
     JOIN exchanges e ON e.id=i.exchange_id LEFT JOIN data_sources ds ON ds.id=c.source_id
     WHERE c.instrument_id=? AND i.isin=? AND e.code='NSE' AND i.active AND i.listing_status='ACTIVE'
       AND c.timeframe='1d' AND (c.candle_time AT TIME ZONE 'Asia/Kolkata')::date BETWEEN ? AND ?
     ORDER BY c.candle_time
     """,id.longValue(),isin,today.minusDays(470),today.minusDays(1));
   var stock=history.stream().map(m->new Point(day(m.get("trade_date")),(BigDecimal)m.get("close"),
      (String)m.get("source_code"),Boolean.TRUE.equals(m.get("eligible")))).toList();
   var result=new LinkedHashMap<>(compare(stock,benchmark,calendar,today));
   Map<String,Object> sectorWindows=new LinkedHashMap<>();
   sectors.forEach((key,points)->{
     var matched=compare(stock,points,calendar,today);
     if("MATCHED_PRICE_INDEX_OBSERVATIONS".equals(matched.get("status"))){
       var sector=new LinkedHashMap<>(matched);
       sector.put("benchmark_key",key);
       sectorWindows.put(key,sector);
     }
   });
   result.put("sector_candidates_internal",sectorWindows);
   out.put("NSE:"+isin+":"+id.longValue(),result);
  }
  return out;
 }
 static Map<String,Object> compare(List<Point> stock,List<Point> benchmark,NavigableMap<LocalDate,String> calendar,LocalDate today){
  var windows=new LinkedHashMap<String,Object>();
  var s=index(stock);var b=index(benchmark);
  LocalDate terminal=today.minusDays(1);
  List<LocalDate> dates=new ArrayList<>();
  // Require each calendar day through the latest completed regular session.
  // A missing day or special session breaks the contiguous research interval.
  for(int i=0;i<470;i++){
   LocalDate d=terminal.minusDays(i);String state=calendar.get(d);
   if("REGULAR".equals(state))dates.add(d);
   else if(!"CLOSED".equals(state))break;
  }
  if(!dates.isEmpty()&&!dates.getFirst().isBefore(today.minusDays(5)))for(int n:new int[]{20,60,120,252}){
   if(dates.size()<n+1)continue;
   var expected=dates.subList(0,n+1);LocalDate first=expected.getLast(),last=expected.getFirst();
   var expectedSet=new HashSet<>(expected);
   if(!s.subMap(first,true,last,true).keySet().equals(expectedSet)||!b.subMap(first,true,last,true).keySet().equals(expectedSet))continue;
   if(expected.stream().anyMatch(d->!valid(s.get(d))||!valid(b.get(d))))continue;
   double stockReturn=change(s.get(first),s.get(last)),indexReturn=change(b.get(first),b.get(last));
   if(!Double.isFinite(stockReturn)||!Double.isFinite(indexReturn)||Math.abs(stockReturn)>1e9||Math.abs(indexReturn)>1e9)continue;
   windows.put(String.valueOf(n),Map.of("first_date",first.toString(),"last_date",last.toString(),
     "stock_return_percent",round(stockReturn),"index_return_percent",round(indexReturn),"difference_pp",round(stockReturn-indexReturn),"dates_digest",digest(expected)));
  }
  return Map.of("status",windows.isEmpty()?"UNAVAILABLE":"MATCHED_PRICE_INDEX_OBSERVATIONS",
    "benchmark_key","NSE_INDEX|Nifty 50","windows",windows,"notice",NOTICE);
 }
 private static NavigableMap<LocalDate,Point> index(List<Point> points){
  var out=new TreeMap<LocalDate,Point>();
  for(Point p:points){
   if(p.date()==null)return new TreeMap<>();
   if(out.putIfAbsent(p.date(),p)!=null)out.put(p.date(),new Point(p.date(),null,null,false));
  }
  return out;
 }
 private static boolean valid(Point p){return p!=null&&p.eligible()&&"UPSTOX".equals(p.source())&&p.close()!=null
   &&p.close().signum()>0&&Double.isFinite(p.close().doubleValue());}
 private static double change(Point first,Point last){return 100*(last.close().doubleValue()/first.close().doubleValue()-1);}
 private static String digest(List<LocalDate> dates){
  try{
   String joined=String.join("\n",dates.reversed().stream().map(LocalDate::toString).toList());
   return HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(joined.getBytes(java.nio.charset.StandardCharsets.UTF_8)));
  }catch(java.security.NoSuchAlgorithmException ex){throw new IllegalStateException(ex);}
 }
 private static double round(double value){return Math.round(value*10000d)/10000d;}
}
