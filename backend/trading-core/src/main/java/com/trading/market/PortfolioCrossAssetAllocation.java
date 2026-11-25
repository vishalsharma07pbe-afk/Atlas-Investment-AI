package com.trading.market;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;

/** Bounded local mixed-asset research; never treats NAVs as adjusted stock closes. */
final class PortfolioCrossAssetAllocation {
  private PortfolioCrossAssetAllocation(){}
  record NavSeries(String source,Map<PortfolioEquityCorrelation.Interval,Double> returns){}
  private static Map<String,Object> unavailable(String status){
    return Map.of("status",status,"alternatives",List.of(),
      "notice","Mixed-asset historical research requires complete recent exact recorded valuations, validated adjusted equity closes and current exact Growth scheme NAV history. Missing evidence is not a low-risk result.");
  }
  static Map<String,Object> collect(JdbcTemplate jdbc,List<Map<String,Object>> rows,
      Map<String,Map<PortfolioEquityCorrelation.Interval,Double>> equitySeries,LocalDate today){
    if(rows.stream().noneMatch(row->"EQUITY".equals(row.get("asset_type")))||
        rows.stream().noneMatch(row->"MUTUAL_FUND".equals(row.get("asset_type"))))
      return unavailable("NO_MIXED_POSITIVE_HOLDINGS");
    Map<String,BigDecimal> values=new TreeMap<>();
    Map<String,String> symbols=new TreeMap<>();
    Map<String,Long> fundCodes=new TreeMap<>();
    boolean complete=true,hasEquity=false,hasFund=false;
    for(var row:rows){
      String type=String.valueOf(row.get("asset_type"));
      if(!(row.get("market_value") instanceof BigDecimal v)||v.signum()<0||!Double.isFinite(v.doubleValue())||
          !Boolean.TRUE.equals(row.get("recorded_valuation_recent"))){complete=false;continue;}
      if(v.signum()==0)continue;
      String key;
      if("EQUITY".equals(type)){
        hasEquity=true;
        if(!(row.get("isin") instanceof String isin)||!isin.matches("INE[A-Z0-9]{9}")||
            !(row.get("instrument_id") instanceof Number)){complete=false;continue;}
        key=isin;
      }else if("MUTUAL_FUND".equals(type)){
        hasFund=true;
        if(!(row.get("exact_scheme_code") instanceof Number code)||
            !String.valueOf(code.longValue()).matches("[1-9][0-9]{5,8}")||
            !String.valueOf(code.longValue()).equals(row.get("symbol"))){complete=false;continue;}
        key="AMFI:"+code.longValue();fundCodes.put(key,code.longValue());
      }else{complete=false;continue;}
      values.merge(key,v,BigDecimal::add);
      symbols.putIfAbsent(key,String.valueOf(row.get("symbol")));
    }
    if(!complete)return unavailable("INSUFFICIENT_RECENT_EXACT_MIXED_COVERAGE");
    if(!hasEquity||!hasFund)return unavailable("NO_MIXED_POSITIVE_HOLDINGS");
    if(values.size()>12)return unavailable("INSUFFICIENT_RECENT_EXACT_MIXED_COVERAGE");
    var series=new HashMap<>(equitySeries);
    Map<String,String> navSources=new TreeMap<>();
    for(var entry:fundCodes.entrySet()){
      var history=jdbc.queryForList("""
        SELECT n.nav_date,n.nav,n.source_code FROM mutual_fund_nav n
        JOIN mutual_fund_schemes s ON s.scheme_code=n.scheme_code
        WHERE n.scheme_code=? AND s.amfi_option='GROWTH'
          AND s.amfi_plan IN ('DIRECT','REGULAR') AND s.isin_growth ~ '^IN[A-Z0-9]{10}$'
          AND s.amfi_metadata_date BETWEEN ?::date-7 AND ?::date
          AND n.nav_date BETWEEN ?::date-90 AND ?::date-1
          AND n.source_code IN ('AMFI','MFAPI')
        ORDER BY n.nav_date LIMIT 100
        """,entry.getValue(),today,today,today,today);
      NavSeries nav=navReturns(history,today);
      if(nav!=null){series.put(entry.getKey(),nav.returns());navSources.put(entry.getKey(),nav.source());}
    }
    var report=PortfolioHistoricalAllocation.assessMixed(values,symbols,series,today,true);
    report.put("nav_sources",navSources);
    report.put("equity_identity_count",values.size()-fundCodes.size());
    report.put("fund_identity_count",fundCodes.size());
    return report;
  }
  static NavSeries navReturns(List<Map<String,Object>> rows,LocalDate today){
    Map<String,NavigableMap<LocalDate,Double>> sources=new HashMap<>();
    Set<LocalDate> seen=new HashSet<>();
    for(var row:rows){
      Object date=row.get("nav_date");
      LocalDate day=date instanceof java.sql.Date d?d.toLocalDate():date instanceof LocalDate d?d:null;
      String source=String.valueOf(row.get("source_code"));
      if(day==null||day.isBefore(today.minusDays(90))||!day.isBefore(today)||!seen.add(day)||
          !Set.of("AMFI","MFAPI").contains(source)||!(row.get("nav") instanceof Number n))return null;
      double nav=n.doubleValue();
      if(!Double.isFinite(nav)||nav<=0)return null;
      sources.computeIfAbsent(source,k->new TreeMap<>()).put(day,nav);
    }
    // Prefer a complete eligible AMFI series; never splice different sources.
    for(String source:List.of("AMFI","MFAPI")){
      var prices=sources.get(source);
      if(prices==null||prices.size()<31||prices.lastKey().isBefore(today.minusDays(5)))continue;
      var result=new HashMap<PortfolioEquityCorrelation.Interval,Double>();
      LocalDate prior=null;double previous=0;
      for(var p:prices.entrySet()){
        if(prior!=null&&ChronoUnit.DAYS.between(prior,p.getKey())<=7){
          double ret=p.getValue()/previous-1;
          if(!Double.isFinite(ret)||ret<=-1)return null;
          result.put(new PortfolioEquityCorrelation.Interval(prior,p.getKey()),ret);
        }
        prior=p.getKey();previous=p.getValue();
      }
      if(result.size()>=30)return new NavSeries(source,result);
    }
    return null;
  }
}
