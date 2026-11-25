package com.trading.market;
import com.fasterxml.jackson.databind.*;
import java.math.*;
import java.time.*;
import java.time.format.*;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
@Service public class AmfiFeedService {
 private final JdbcTemplate jdbc;private final FeedHttp http;private final ObjectMapper json=new ObjectMapper();
 public AmfiFeedService(JdbcTemplate jdbc,FeedHttp http){this.jdbc=jdbc;this.http=http;}
 @Transactional(rollbackFor=Exception.class)
 public int refresh()throws Exception{return importNav(http.text("https://portal.amfiindia.com/spages/NAVAll.txt",null,20_000_000));}
 @Transactional(rollbackFor=Exception.class)
 public int importNav(String raw){
  String amc="",category="";int count=0;
  Set<Long> seen=new HashSet<>();
  LocalDate today=LocalDate.now(MarketCalendarService.IST);
  for(String line:raw.split("\\R")){
   line=line.trim();if(line.isBlank())continue;
   if(!line.contains(";")){
    if(line.endsWith("Mutual Fund"))amc=line;
    else if(line.contains("Scheme")||line.contains("Open Ended")||line.contains("Close Ended")){category=line;amc="";}
    continue;
   }
   String[] p=line.split(";",-1);if((p.length!=6&&p.length!=8)||!p[0].trim().matches("\\d+"))continue;
   try{
    long code=Long.parseLong(p[0].trim());
    if(code<=0||code>999999999)continue;
    if(!seen.add(code))throw new IllegalStateException("Duplicate AMFI scheme code");
    int navIndex=p.length==8?6:4,dateIndex=p.length==8?7:5;
    String name=p[3].trim();
    if(p.length==8)name=java.util.stream.Stream.of(p[3],p[4],p[5]).map(String::trim).filter(value->!value.isBlank()).reduce((x,y)->x+" - "+y).orElse("");
    if(name.isBlank()||name.length()>500)continue;
    BigDecimal nav=new BigDecimal(p[navIndex].trim());if(nav.signum()<=0||nav.compareTo(new BigDecimal("1000000000"))>0)continue;
    LocalDate date=LocalDate.parse(p[dateIndex].trim(),DateTimeFormatter.ofPattern("dd-MMM-uuuu",Locale.ENGLISH).withResolverStyle(ResolverStyle.STRICT));
    if(date.isAfter(today))continue;
    String plan=p.length==8?explicitPlan(p[4]):null;
    String option=p.length==8?explicitOption(p[5]):null;
    String isin1=isin(p[1]),isin2=isin(p[2]);
    int mapped=jdbc.update("""
      INSERT INTO mutual_fund_schemes(scheme_code,scheme_name,isin_growth,isin_reinvestment,amc_name,category,amfi_plan,amfi_option,amfi_metadata_date)
      VALUES (?,?,?,?,?,?,?,?,?)
      ON CONFLICT(scheme_code) DO UPDATE SET scheme_name=EXCLUDED.scheme_name,
        isin_growth=coalesce(EXCLUDED.isin_growth,mutual_fund_schemes.isin_growth),
        isin_reinvestment=coalesce(EXCLUDED.isin_reinvestment,mutual_fund_schemes.isin_reinvestment),
        amc_name=EXCLUDED.amc_name,category=EXCLUDED.category,
        amfi_plan=EXCLUDED.amfi_plan,amfi_option=EXCLUDED.amfi_option,amfi_metadata_date=EXCLUDED.amfi_metadata_date,last_synced_at=now()
      WHERE (mutual_fund_schemes.amfi_metadata_date IS NULL OR EXCLUDED.amfi_metadata_date>=mutual_fund_schemes.amfi_metadata_date)
        AND (EXCLUDED.isin_growth IS NULL OR nullif(mutual_fund_schemes.isin_growth,'-') IS NULL
          OR mutual_fund_schemes.isin_growth='' OR mutual_fund_schemes.isin_growth=EXCLUDED.isin_growth)
        AND (EXCLUDED.isin_reinvestment IS NULL OR nullif(mutual_fund_schemes.isin_reinvestment,'-') IS NULL
          OR mutual_fund_schemes.isin_reinvestment='' OR mutual_fund_schemes.isin_reinvestment=EXCLUDED.isin_reinvestment)
      """,code,name,isin1,isin2,amc,category,plan,option,date);
    if(mapped!=1)continue;
    jdbc.update("INSERT INTO mutual_fund_nav(scheme_code,nav_date,nav,source_code) VALUES (?,?,?,'AMFI') ON CONFLICT(scheme_code,nav_date) DO UPDATE SET nav=EXCLUDED.nav,source_code='AMFI',received_at=now()",code,date,nav);
    count++;
   }catch(NumberFormatException|DateTimeParseException ignored){}
  }
  if(count==0)throw new IllegalStateException("AMFI feed has no valid NAV rows");
  return count;
 }
 private static String isin(String value){
  String s=value.trim();return s.matches("IN[A-Z0-9]{10}")?s:null;
 }
 private static String explicitPlan(String value){
  return switch(value.trim().toUpperCase(Locale.ROOT)){case "DIRECT","DIRECT PLAN"->"DIRECT";case "REGULAR","REGULAR PLAN"->"REGULAR";default->null;};
 }
 private static String explicitOption(String value){
  return switch(value.trim().toUpperCase(Locale.ROOT)){case "GROWTH","GROWTH OPTION"->"GROWTH";case "IDCW","IDCW OPTION"->"IDCW";default->null;};
 }
 public List<Map<String,Object>> search(String q){
  if(q==null||q.trim().length()<2||q.length()>100)throw new IllegalArgumentException("Search must be 2..100 characters");
  return jdbc.queryForList("SELECT s.*,n.nav,n.nav_date FROM mutual_fund_schemes s LEFT JOIN LATERAL (SELECT nav,nav_date FROM mutual_fund_nav WHERE scheme_code=s.scheme_code ORDER BY nav_date DESC LIMIT 1) n ON true WHERE s.scheme_name ILIKE ? OR s.scheme_code::text=? ORDER BY s.scheme_name LIMIT 50","%"+q.trim()+"%",q.trim());
 }
 @Transactional(rollbackFor=Exception.class)
 public int history(long code)throws Exception{
  if(code<=0||code>999999999)throw new IllegalArgumentException("Invalid scheme code");
  JsonNode root=json.readTree(http.text("https://api.mfapi.in/mf/"+code,null,12_000_000));
  if(!root.isObject()||(root.has("status")&&!"SUCCESS".equalsIgnoreCase(root.path("status").asText())))
    throw new IllegalStateException("History provider rejected request");
  JsonNode meta=root.path("meta");
  if(!Long.toString(code).equals(meta.path("scheme_code").asText()))throw new IllegalStateException("History scheme mismatch");
  JsonNode rows=root.path("data");if(!rows.isArray()||rows.isEmpty()||rows.size()>30000)throw new IllegalStateException("Invalid historical NAV");
  Map<LocalDate,BigDecimal> validated=new TreeMap<>();
  LocalDate today=LocalDate.now(MarketCalendarService.IST);
  for(JsonNode row:rows){
   try{
    LocalDate day=LocalDate.parse(row.path("date").asText(),DateTimeFormatter.ofPattern("dd-MM-uuuu").withResolverStyle(ResolverStyle.STRICT));
    BigDecimal nav=new BigDecimal(row.path("nav").asText());
    if(nav.signum()<=0||nav.compareTo(new BigDecimal("1000000000"))>0||day.isAfter(today))continue;
    BigDecimal previous=validated.putIfAbsent(day,nav);
    if(previous!=null&&previous.compareTo(nav)!=0)throw new IllegalStateException("Conflicting historical NAV observations");
   }catch(NumberFormatException|DateTimeParseException ignored){}
  }
  if(validated.isEmpty())throw new IllegalStateException("No valid historical NAV");
  for(var row:validated.entrySet()){
   jdbc.update("INSERT INTO mutual_fund_nav(scheme_code,nav_date,nav,source_code) VALUES (?,?,?,'MFAPI') ON CONFLICT(scheme_code,nav_date) DO UPDATE SET nav=EXCLUDED.nav,received_at=now() WHERE mutual_fund_nav.source_code='MFAPI'",code,row.getKey(),row.getValue());
  }
  return validated.size();
 }
 public Map<String,Object> performance(long code){
  List<Map<String,Object>> rows=jdbc.queryForList("SELECT nav_date,nav FROM mutual_fund_nav WHERE scheme_code=? ORDER BY nav_date",code);
  if(rows.isEmpty())return Map.of("schemeCode",code,"status","NO_HISTORY");
  BigDecimal peak=BigDecimal.ZERO,worst=BigDecimal.ZERO;for(var row:rows){BigDecimal nav=(BigDecimal)row.get("nav");peak=peak.max(nav);BigDecimal dd=nav.divide(peak,12,RoundingMode.HALF_UP).subtract(BigDecimal.ONE);worst=worst.min(dd);}
  LocalDate latest=((java.sql.Date)rows.get(rows.size()-1).get("nav_date")).toLocalDate();BigDecimal current=(BigDecimal)rows.get(rows.size()-1).get("nav");
  Map<String,Object> out=new LinkedHashMap<>();out.put("schemeCode",code);out.put("asOf",latest);out.put("nav",current);out.put("maxDrawdown",worst);
  for(int years:List.of(1,3,5)){
   LocalDate target=latest.minusYears(years);Map<String,Object> prior=null;
   for(var row:rows){LocalDate day=((java.sql.Date)row.get("nav_date")).toLocalDate();if(!day.isAfter(target))prior=row;else break;}
   if(prior==null){out.put("cagr"+years+"Y",null);continue;}
   BigDecimal old=(BigDecimal)prior.get("nav");LocalDate day=((java.sql.Date)prior.get("nav_date")).toLocalDate();
   double elapsed=java.time.temporal.ChronoUnit.DAYS.between(day,latest)/365.2425;
   out.put("cagr"+years+"Y",Math.pow(current.doubleValue()/old.doubleValue(),1.0/elapsed)-1);
  }
  for(int years:List.of(1,3)){
   LocalDate earliest=latest.minusYears(years);List<Double> rolling=new ArrayList<>();
   for(int i=0;i<rows.size();i++){
    LocalDate end=((java.sql.Date)rows.get(i).get("nav_date")).toLocalDate();
    if(end.isBefore(earliest))continue;
    LocalDate start=end.minusYears(years);Map<String,Object> prior=null;
    for(int j=0;j<i;j++){LocalDate date=((java.sql.Date)rows.get(j).get("nav_date")).toLocalDate();if(!date.isAfter(start))prior=rows.get(j);else break;}
    if(prior==null)continue;
    BigDecimal startNav=(BigDecimal)prior.get("nav"),endNav=(BigDecimal)rows.get(i).get("nav");
    double days=java.time.temporal.ChronoUnit.DAYS.between(((java.sql.Date)prior.get("nav_date")).toLocalDate(),end);
    if(days>0)rolling.add(Math.pow(endNav.doubleValue()/startNav.doubleValue(),365.2425/days)-1);
   }
   out.put("rolling"+years+"Y",rolling);
  }
  return out;
 }
}
