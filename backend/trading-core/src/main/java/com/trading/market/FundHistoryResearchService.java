package com.trading.market;

import java.time.*;
import java.time.temporal.ChronoUnit;
import java.math.BigDecimal;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;

/** Automatic research of explicitly identified AMFI Direct Growth schemes. */
@Service
public class FundHistoryResearchService {
  private final JdbcTemplate jdbc;
  private final AmfiFeedService funds;
  @Value("${ATLAS_MF_HISTORY_AUTO_REFRESH_ENABLED:false}") boolean enabled;
  @Value("${MARKET_DATA_USAGE_RIGHTS_CONFIRMED:false}") boolean permitted;
  public FundHistoryResearchService(JdbcTemplate jdbc,AmfiFeedService funds){this.jdbc=jdbc;this.funds=funds;}

  static final Map<String,String> CATEGORIES=Map.of("LARGE_CAP","large cap fund",
    "MID_CAP","mid cap fund","SMALL_CAP","small cap fund","FLEXI_CAP","flexi cap fund","INDEX","index funds");
  static final String UNIVERSE="""
    FROM mutual_fund_schemes s
    WHERE lower(trim(s.category)) LIKE ?
      AND s.scheme_name ~* '(^|[^a-z])direct([^a-z]|$)'
      AND s.scheme_name ~* '(^|[^a-z])growth([^a-z]|$)'
      AND s.scheme_name !~* '(idcw|dividend|regular|bonus)'
    """;

  private static String categoryPattern(String category){
    String label=CATEGORIES.get(category);
    if(label==null)throw new IllegalArgumentException("UNSUPPORTED_CATEGORY");
    return "% - "+label+")%";
  }

  @Scheduled(initialDelayString="${atlas.funds.history.initial-ms:90000}",
             fixedDelayString="${atlas.funds.history.poll-ms:900000}")
  public void scheduled(){
    if(!enabled||!permitted)return;
    LocalDate today=LocalDate.now(MarketCalendarService.IST);
    for(String category:List.of("LARGE_CAP","MID_CAP","SMALL_CAP","FLEXI_CAP","INDEX")){
      var rows=jdbc.queryForList("SELECT s.scheme_code "+UNIVERSE+"""
        AND EXISTS(SELECT 1 FROM mutual_fund_nav n WHERE n.scheme_code=s.scheme_code
          AND n.source_code='AMFI' AND n.nav_date BETWEEN ?::date-7 AND ?::date)
        AND NOT EXISTS(SELECT 1 FROM fund_history_attempts a WHERE a.scheme_code=s.scheme_code AND a.next_attempt_at>now())
        AND (SELECT count(*) FROM mutual_fund_nav n WHERE n.scheme_code=s.scheme_code
          AND n.nav_date BETWEEN ?::date-1100 AND ?::date)<650
        ORDER BY (SELECT attempted_at FROM fund_history_attempts a WHERE a.scheme_code=s.scheme_code)
          ASC NULLS FIRST,s.scheme_code LIMIT 1
        """,categoryPattern(category),today,today,today,today);
      for(var row:rows){
        long code=((Number)row.get("scheme_code")).longValue();
        int claimed=jdbc.update("""
          INSERT INTO fund_history_attempts(scheme_code,attempted_at,next_attempt_at,status)
          VALUES (?,now(),now()+interval '1 day','RUNNING')
          ON CONFLICT(scheme_code) DO UPDATE SET attempted_at=now(),next_attempt_at=now()+interval '1 day',status='RUNNING'
          WHERE fund_history_attempts.next_attempt_at<=now()
          """,code);
        if(claimed==0)continue;
        try{
          int written=funds.history(code);
          jdbc.update("UPDATE fund_history_attempts SET status=?,next_attempt_at=now()+interval '7 days' WHERE scheme_code=?",written>0?"SUCCESS":"FAILED",code);
        }catch(Exception ex){
          jdbc.update("UPDATE fund_history_attempts SET status='FAILED',next_attempt_at=now()+interval '1 day' WHERE scheme_code=?",code);
        }
      }
    }
  }

  /** Bounded local read model. No external request or user data. */
  public Map<String,Object> watch(String category){
    String pattern=categoryPattern(category);
    LocalDate today=LocalDate.now(MarketCalendarService.IST);
    int universe=jdbc.queryForObject("SELECT count(*) "+UNIVERSE,Integer.class,pattern);
    var sample=jdbc.queryForList("SELECT s.scheme_code,s.scheme_name,s.category "+UNIVERSE+"""
      AND EXISTS(SELECT 1 FROM mutual_fund_nav n WHERE n.scheme_code=s.scheme_code
        AND n.source_code='AMFI' AND n.nav_date BETWEEN ?::date-7 AND ?::date)
      ORDER BY (SELECT count(*) FROM mutual_fund_nav n WHERE n.scheme_code=s.scheme_code
        AND n.nav_date BETWEEN ?::date-1100 AND ?::date) DESC,s.scheme_code LIMIT 40
      """,pattern,today,today,today,today);
    List<Map<String,Object>> observations=new ArrayList<>();
    for(var fund:sample){
      var rows=jdbc.queryForList("""
        SELECT nav_date,nav,source_code FROM mutual_fund_nav
        WHERE scheme_code=? AND nav_date BETWEEN ?::date-1120 AND ?::date
          AND source_code IN ('AMFI','MFAPI') ORDER BY nav_date
        """,fund.get("scheme_code"),today,today);
      var metrics=metrics(rows,today);
      if(metrics==null)continue;
      metrics.putAll(fund);observations.add(metrics);
    }
    observations.sort(Comparator.comparingDouble((Map<String,Object> row)->((Number)row.get("cagr_3y_percent")).doubleValue()).reversed()
      .thenComparingLong(row->((Number)row.get("scheme_code")).longValue()));
    return Map.of("category",category,"status",observations.isEmpty()?"COLLECTING_HISTORY":"HISTORICAL_WATCH_ONLY",
      "universe_count",universe,"sample_count",sample.size(),"eligible_count",observations.size(),
      "items",observations.stream().limit(5).toList(),"automatic_collection_enabled",enabled&&permitted,
      "notice","Bounded AMFI-category Direct Growth sample ranked by trailing three-year CAGR, not a recommendation. Expense ratios, benchmarks, riskometer and holdings evidence remain unverified.");
  }

  static Map<String,Object> metrics(List<Map<String,Object>> rows,LocalDate today){
    if(rows.size()<650)return null;
    var last=rows.getLast();
    LocalDate end=date(last.get("nav_date"));
    if(end==null||end.isAfter(today)||end.isBefore(today.minusDays(7))||!"AMFI".equals(last.get("source_code")))return null;
    LocalDate target3=end.minusYears(3),target1=end.minusYears(1),prior=null;
    double current=((BigDecimal)last.get("nav")).doubleValue(),base3=0,base1=0,peak=0,drawdown=0;
    LocalDate start3=null,start1=null;
    int count=0;
    for(var row:rows){
      LocalDate d=date(row.get("nav_date"));
      double nav=((BigDecimal)row.get("nav")).doubleValue();
      if(d==null||!Double.isFinite(nav)||nav<=0||d.isAfter(end)||prior!=null&&!d.isAfter(prior))return null;
      if(!d.isAfter(target3)){base3=nav;start3=d;}
      if(!d.isAfter(target1)){base1=nav;start1=d;}
      if(!d.isBefore(target3)){
        if(prior!=null&&ChronoUnit.DAYS.between(prior,d)>14)return null;
        peak=Math.max(peak,nav);drawdown=Math.min(drawdown,nav/peak-1);count++;
      }
      prior=d;
    }
    if(count<650||start3==null||start1==null||start3.isBefore(target3.minusDays(14))||start1.isBefore(target1.minusDays(14)))return null;
    Map<String,Object> result=new LinkedHashMap<>();
    result.put("nav",current);result.put("nav_date",end.toString());
    result.put("cagr_3y_percent",round(100*(Math.pow(current/base3,365.2425/ChronoUnit.DAYS.between(start3,end))-1)));
    result.put("cagr_1y_percent",round(100*(Math.pow(current/base1,365.2425/ChronoUnit.DAYS.between(start1,end))-1)));
    result.put("drawdown_3y_percent",round(drawdown*100));result.put("observations",count);
    result.put("sources",rows.stream().map(r->String.valueOf(r.get("source_code"))).distinct().sorted().toList());
    return result;
  }
  private static LocalDate date(Object d){return d instanceof java.sql.Date x?x.toLocalDate():d instanceof LocalDate x?x:null;}
  private static double round(double n){return Math.round(n*10000d)/10000d;}
}
