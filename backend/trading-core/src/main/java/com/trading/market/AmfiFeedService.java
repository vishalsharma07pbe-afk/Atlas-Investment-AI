package com.trading.market;
import com.fasterxml.jackson.databind.*;
import java.math.*;
import java.time.*;
import java.time.format.*;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
@Service public class AmfiFeedService {
 private final JdbcTemplate jdbc;private final FeedHttp http;private final ObjectMapper json=new ObjectMapper();
 public AmfiFeedService(JdbcTemplate jdbc,FeedHttp http){this.jdbc=jdbc;this.http=http;}
 public int refresh()throws Exception{return importNav(http.text("https://portal.amfiindia.com/spages/NAVAll.txt",null,20_000_000));}
 public int importNav(String raw){
  String amc="",category="";int count=0;
  for(String line:raw.split("\\R")){
   line=line.trim();if(line.isBlank())continue;
   if(!line.contains(";")){if(line.endsWith("Mutual Fund"))amc=line;else if(line.contains("Scheme")||line.contains("Open Ended")||line.contains("Close Ended"))category=line;continue;}
   String[] p=line.split(";",-1);if(p.length<6||!p[0].trim().matches("\\d+"))continue;
   try{
    long code=Long.parseLong(p[0].trim());
    // AMFI added separate Plan and Option columns in 2026. Accept both the
    // legacy six-column file and the current eight-column official format.
    int navIndex=p.length>=8?6:4,dateIndex=p.length>=8?7:5;
    String name=p[3].trim();
    if(p.length>=8)name=java.util.stream.Stream.of(p[3],p[4],p[5]).map(String::trim).filter(value->!value.isBlank()).reduce((a,b)->a+" - "+b).orElse("");
    if(name.isBlank())continue;
    BigDecimal nav=new BigDecimal(p[navIndex].trim());if(nav.signum()<=0)continue;
    LocalDate date=LocalDate.parse(p[dateIndex].trim(),DateTimeFormatter.ofPattern("dd-MMM-yyyy",Locale.ENGLISH));
    jdbc.update("INSERT INTO mutual_fund_schemes(scheme_code,scheme_name,isin_growth,isin_reinvestment,amc_name,category) VALUES (?,?,?,?,?,?) ON CONFLICT(scheme_code) DO UPDATE SET scheme_name=EXCLUDED.scheme_name,isin_growth=EXCLUDED.isin_growth,isin_reinvestment=EXCLUDED.isin_reinvestment,amc_name=EXCLUDED.amc_name,category=EXCLUDED.category,last_synced_at=now()",code,name,p[1].trim(),p[2].trim(),amc,category);
    jdbc.update("INSERT INTO mutual_fund_nav(scheme_code,nav_date,nav,source_code) VALUES (?,?,?,'AMFI') ON CONFLICT(scheme_code,nav_date) DO UPDATE SET nav=EXCLUDED.nav,source_code='AMFI',received_at=now()",code,date,nav);
    count++;
   }catch(NumberFormatException|DateTimeParseException ignored){/* malformed source row is skipped */}
  }
  if(count==0)throw new IllegalStateException("AMFI feed has no valid NAV rows");
  return count;
 }
 public List<Map<String,Object>> search(String q){
  if(q==null||q.trim().length()<2||q.length()>100)throw new IllegalArgumentException("Search must be 2..100 characters");
  return jdbc.queryForList("SELECT s.*,n.nav,n.nav_date FROM mutual_fund_schemes s LEFT JOIN LATERAL (SELECT nav,nav_date FROM mutual_fund_nav WHERE scheme_code=s.scheme_code ORDER BY nav_date DESC LIMIT 1) n ON true WHERE s.scheme_name ILIKE ? OR s.scheme_code::text=? ORDER BY s.scheme_name LIMIT 50","%"+q.trim()+"%",q.trim());
 }
 public int history(long code)throws Exception{
  JsonNode root=json.readTree(http.text("https://api.mfapi.in/mf/"+code,null,12_000_000));
  JsonNode rows=root.path("data");if(!rows.isArray()||rows.isEmpty())throw new IllegalStateException("No historical NAV");
  int count=0;
  for(JsonNode row:rows){
   try{
    LocalDate day=LocalDate.parse(row.path("date").asText(),DateTimeFormatter.ofPattern("dd-MM-yyyy"));
    BigDecimal nav=new BigDecimal(row.path("nav").asText());
    if(nav.signum()<=0)continue;
    jdbc.update("INSERT INTO mutual_fund_nav(scheme_code,nav_date,nav,source_code) VALUES (?,?,?,'MFAPI') ON CONFLICT(scheme_code,nav_date) DO UPDATE SET nav=EXCLUDED.nav,received_at=now()",code,day,nav);count++;
   }catch(NumberFormatException|DateTimeParseException ignored){}
  }
  return count;
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
