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
    // Prioritize the exact saved scheme, including regular, debt and other plans
    // outside the discovery universe. Only public scheme codes are selected.
    collectHeld(today);
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
      for(var row:rows)collect(((Number)row.get("scheme_code")).longValue());
    }
  }

  private void collectHeld(LocalDate today){
    var rows=jdbc.queryForList("""
      SELECT s.scheme_code FROM mutual_fund_schemes s
      WHERE EXISTS(SELECT 1 FROM personal_holdings h
        WHERE h.asset_type='MUTUAL_FUND' AND h.user_id IS NOT NULL
          AND h.symbol=s.scheme_code::text)
        AND EXISTS(SELECT 1 FROM mutual_fund_nav n WHERE n.scheme_code=s.scheme_code
          AND n.source_code='AMFI' AND n.nav_date BETWEEN ?::date-7 AND ?::date)
        AND NOT EXISTS(SELECT 1 FROM fund_history_attempts a WHERE a.scheme_code=s.scheme_code AND a.next_attempt_at>now())
        AND ((SELECT count(*) FROM mutual_fund_nav n WHERE n.scheme_code=s.scheme_code
          AND n.source_code IN ('AMFI','MFAPI') AND n.nav_date BETWEEN ?::date-1100 AND ?::date)<650
          OR NOT EXISTS(SELECT 1 FROM mutual_fund_nav n WHERE n.scheme_code=s.scheme_code
            AND n.source_code IN ('AMFI','MFAPI')
            AND n.nav_date BETWEEN (?::date-interval '3 years'-interval '21 days')::date
              AND (?::date-interval '3 years')::date))
      ORDER BY (SELECT attempted_at FROM fund_history_attempts a WHERE a.scheme_code=s.scheme_code)
        ASC NULLS FIRST,s.scheme_code LIMIT 2
      """,today,today,today,today,today,today);
    for(var row:rows)collect(((Number)row.get("scheme_code")).longValue());
  }

  private void collect(long code){
    int claimed=jdbc.update("""
      INSERT INTO fund_history_attempts(scheme_code,attempted_at,next_attempt_at,status)
      VALUES (?,now(),now()+interval '1 day','RUNNING')
      ON CONFLICT(scheme_code) DO UPDATE SET attempted_at=now(),next_attempt_at=now()+interval '1 day',status='RUNNING'
      WHERE fund_history_attempts.next_attempt_at<=now()
      """,code);
    if(claimed==0)return;
    try{
      int written=funds.history(code);
      jdbc.update("UPDATE fund_history_attempts SET status=?,next_attempt_at=now()+interval '7 days' WHERE scheme_code=?",written>0?"SUCCESS":"FAILED",code);
    }catch(Exception ex){
      jdbc.update("UPDATE fund_history_attempts SET status='FAILED',next_attempt_at=now()+interval '1 day' WHERE scheme_code=?",code);
    }
  }

  /** Bounded local read model. No external request or user data. */
  public Map<String,Object> watch(String category){
    String pattern=categoryPattern(category);
    LocalDate today=LocalDate.now(MarketCalendarService.IST);
    int universe=jdbc.queryForObject("SELECT count(*) "+UNIVERSE,Integer.class,pattern);
    // A shared official NAV date prevents comparing different trailing windows.
    LocalDate commonEnd=jdbc.query("SELECT max((SELECT max(n.nav_date) FROM mutual_fund_nav n WHERE n.scheme_code=s.scheme_code AND n.source_code='AMFI' AND n.nav_date BETWEEN ?::date-7 AND ?::date)) "+UNIVERSE,
      rs->{if(!rs.next())return null;var d=rs.getDate(1);return d==null?null:d.toLocalDate();},today,today,pattern);
    var sample=jdbc.queryForList("SELECT s.scheme_code,s.scheme_name,s.category "+UNIVERSE+"""
      AND EXISTS(SELECT 1 FROM mutual_fund_nav n WHERE n.scheme_code=s.scheme_code
        AND n.source_code='AMFI' AND n.nav_date BETWEEN ?::date-7 AND ?::date)
      ORDER BY (SELECT count(*) FROM mutual_fund_nav n WHERE n.scheme_code=s.scheme_code
        AND n.nav_date BETWEEN ?::date-1100 AND ?::date) DESC,s.scheme_code LIMIT 40
      """,pattern,today,today,today,today);
    List<Map<String,Object>> observations=new ArrayList<>();
    Map<Long,List<Map<String,Object>>> histories=sampledHistories(sample,today);
    for(var fund:sample){
      var rows=histories.getOrDefault(((Number)fund.get("scheme_code")).longValue(),List.of());
      var metrics=metrics(rows,today);
      if(metrics==null||commonEnd==null||!commonEnd.toString().equals(metrics.get("nav_date")))continue;
      metrics.putAll(fund);observations.add(metrics);
    }
    observations.sort(Comparator.comparingDouble((Map<String,Object> row)->((Number)row.get("cagr_3y_percent")).doubleValue()).reversed()
      .thenComparingLong(row->((Number)row.get("scheme_code")).longValue()));
    // Index funds can track entirely different assets/benchmarks, so do not give
    // them a cross-index risk-adjusted rank or category peer percentile.
    boolean comparable=!"INDEX".equals(category);
    if(comparable&&observations.size()>=5){
      for(var row:observations){
        double value=((Number)row.get("cagr_3y_percent")).doubleValue();
        long below=observations.stream().filter(r->((Number)r.get("cagr_3y_percent")).doubleValue()<value).count();
        long equal=observations.stream().filter(r->((Number)r.get("cagr_3y_percent")).doubleValue()==value).count();
        row.put("sample_peer_percentile",round(100.0*(below+(equal-1)/2.0)/(observations.size()-1)));
      }
    }
    var riskRank=observations.stream().filter(row->comparable&&row.get("return_to_drawdown") instanceof Number)
      .sorted(Comparator.comparingDouble((Map<String,Object> row)->((Number)row.get("return_to_drawdown")).doubleValue()).reversed()
        .thenComparingLong(row->((Number)row.get("scheme_code")).longValue())).limit(5).toList();
    Map<String,Object> result=new LinkedHashMap<>();
    result.put("category",category);result.put("status",observations.isEmpty()?"COLLECTING_HISTORY":"HISTORICAL_WATCH_ONLY");
    result.put("universe_count",universe);result.put("sample_count",sample.size());result.put("eligible_count",observations.size());
    result.put("comparison_date",commonEnd==null?null:commonEnd.toString());
    result.put("items",observations.stream().limit(5).toList());result.put("risk_adjusted_items",riskRank);
    result.put("weekly_risk_eligible_count",observations.stream().filter(r->r.get("weekly_volatility_percent")!=null).count());
    result.put("automatic_collection_enabled",enabled&&permitted);
    result.put("notice","Historical observations only, from a bounded same-date AMFI category sample. Return-to-drawdown is CAGR divided by absolute observed maximum drawdown, not Sharpe or a forward forecast. Index funds may track different assets. Official benchmark TRI, TER, Riskometer and holdings evidence are still required.");
    return result;
  }

  // The category sample is capped at 40 by watch(). One bounded query replaces
  // up to 40 round trips; each scheme retains its original chronological series.
  Map<Long,List<Map<String,Object>>> sampledHistories(List<Map<String,Object>> sample,LocalDate today){
    if(sample.isEmpty())return Map.of();
    if(sample.size()>40)throw new IllegalArgumentException("SAMPLE_LIMIT_EXCEEDED");
    String placeholders=String.join(",",Collections.nCopies(sample.size(),"?"));
    List<Object> args=new ArrayList<>();
    for(var fund:sample)args.add(((Number)fund.get("scheme_code")).longValue());
    args.add(today);args.add(today);
    var rows=jdbc.queryForList("""
      SELECT scheme_code,nav_date,nav,source_code FROM mutual_fund_nav
      WHERE scheme_code IN (%s) AND nav_date BETWEEN ?::date-1120 AND ?::date
        AND source_code IN ('AMFI','MFAPI') ORDER BY scheme_code,nav_date
      """.formatted(placeholders),args.toArray());
    Map<Long,List<Map<String,Object>>> grouped=new HashMap<>();
    for(var row:rows)grouped.computeIfAbsent(((Number)row.get("scheme_code")).longValue(),key->new ArrayList<>()).add(row);
    return grouped;
  }

  /** Exact saved scheme only; not a category ranking or forward recommendation. */
  public Map<String,Object> holdingEvidence(long schemeCode){
    LocalDate today=LocalDate.now(MarketCalendarService.IST);
    var schemes=jdbc.queryForList("SELECT scheme_code,scheme_name,category FROM mutual_fund_schemes WHERE scheme_code=?",schemeCode);
    if(schemes.isEmpty())return null;
    var rows=jdbc.queryForList("""
      SELECT nav_date,nav,source_code FROM mutual_fund_nav
      WHERE scheme_code=? AND nav_date BETWEEN ?::date-1120 AND ?::date
        AND source_code IN ('AMFI','MFAPI') ORDER BY nav_date
      """,schemeCode,today,today);
    var result=metrics(rows,today);
    if(result==null)return null;
    result.putAll(schemes.getFirst());
    result.put("notice","Historical NAV observations for the exact saved scheme. Official benchmark, TER, Riskometer and holdings evidence remain unverified.");
    return result;
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
    result.putAll(weeklyRisk(rows,end));
    double annual=((Number)result.get("cagr_3y_percent")).doubleValue();
    // No infinite ratio, and no ratio for effectively flat/no-drawdown histories.
    result.put("return_to_drawdown",annual>0&&drawdown<=-0.01?round(annual/(-100*drawdown)):null);
    result.put("sources",rows.stream().map(r->String.valueOf(r.get("source_code"))).distinct().sorted().toList());
    return result;
  }
  /** Fixed seven-day target dates, using a NAV at most three days earlier.
   * Returns are weekly close proxies (not equally spaced daily returns).
   * No interpolation; any missing/duplicate anchor makes risk unavailable.
   */
  static Map<String,Object> weeklyRisk(List<Map<String,Object>> rows,LocalDate end){
    NavigableMap<LocalDate,Double> series=new TreeMap<>();
    for(var row:rows){
      LocalDate d=date(row.get("nav_date"));Object value=row.get("nav");
      if(d==null||!(value instanceof Number n)||!Double.isFinite(n.doubleValue())||n.doubleValue()<=0||series.putIfAbsent(d,n.doubleValue())!=null)return Map.of();
    }
    List<Double> anchors=new ArrayList<>();LocalDate prior=null;
    for(int i=156;i>=0;i--){
      LocalDate target=end.minusWeeks(i);
      var point=series.floorEntry(target);
      if(point==null||point.getKey().isBefore(target.minusDays(3))||prior!=null&&!point.getKey().isAfter(prior))return Map.of();
      anchors.add(point.getValue());prior=point.getKey();
    }
    double sum=0,sumSq=0,worst=Double.POSITIVE_INFINITY;int positive=0,rolling=0;
    for(int i=1;i<anchors.size();i++){
      double r=anchors.get(i)/anchors.get(i-1)-1;sum+=r;sumSq+=r*r;
      if(i>=52){
        double annual=100*(Math.pow(anchors.get(i)/anchors.get(i-52),365.2425/364)-1);
        if(!Double.isFinite(annual))return Map.of();
        worst=Math.min(worst,annual);if(annual>0)positive++;rolling++;
      }
    }
    int n=anchors.size()-1;double variance=Math.max(0,(sumSq-sum*sum/n)/(n-1));
    double volatility=100*Math.sqrt(variance*52);
    if(!Double.isFinite(volatility))return Map.of();
    return Map.of("weekly_volatility_percent",round(volatility),
      "worst_rolling_52w_annualized_percent",round(worst),
      "positive_rolling_52w_percent",round(100.0*positive/rolling),
      "rolling_windows",rolling,"weekly_intervals",n);
  }
  private static LocalDate date(Object d){return d instanceof java.sql.Date x?x.toLocalDate():d instanceof LocalDate x?x:null;}
  private static double round(double n){return Math.round(n*10000d)/10000d;}
}
