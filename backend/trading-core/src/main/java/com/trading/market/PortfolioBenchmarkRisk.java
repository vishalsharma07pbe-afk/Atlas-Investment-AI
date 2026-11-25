package com.trading.market;

import java.math.*;
import java.time.LocalDate;
import java.util.*;
import static com.trading.market.PortfolioFlowAdjustedPerformance.*;
import static com.trading.market.PortfolioRollingPerformance.BenchmarkPoint;

/** Paired estimates against the NIFTY 50 price reference, not a personalized benchmark. */
public final class PortfolioBenchmarkRisk {
  private PortfolioBenchmarkRisk(){}
  public static final double REVIEW_GAP_PP=-5.0;
  public record Assessment(String status,int matchedWeeks,String from,String through,
      Double portfolioReturnPercent,Double benchmarkReturnPercent,Double relativePercentagePoints,
      Double beta,Double annualizedTrackingErrorPercent,Double informationRatio,
      String attentionStatus){}
  private static Assessment unavailable(String status,int count,LocalDate from,LocalDate through){
    return new Assessment(status,count,from==null?null:from.toString(),through==null?null:through.toString(),
      null,null,null,null,null,null,"INSUFFICIENT_EVIDENCE");
  }

  public static Assessment assess(List<Observation> observations,List<Flow> flows,List<BenchmarkPoint> points,LocalDate today){
    if(observations.isEmpty())return unavailable("UNAVAILABLE_PORTFOLIO_HISTORY",0,null,null);
    LocalDate end=observations.getLast().date(),start=end.minusWeeks(13);
    if(end.isAfter(today)||end.isBefore(today.minusDays(7)))
      return unavailable("UNAVAILABLE_STALE_OR_FUTURE_VALUATION",0,start,end);
    var window=observations.stream().filter(o->!o.date().isBefore(start)).toList();
    if(window.isEmpty()||!window.getFirst().date().equals(start))
      return unavailable("UNAVAILABLE_EXACT_WEEKLY_HISTORY",0,start,end);
    var total=calculate(window,flows);
    if(!"AVAILABLE_ESTIMATE".equals(total.status()))return unavailable(total.status(),0,start,end);
    var reference=new TreeMap<LocalDate,BigDecimal>();String source=null;
    for(var p:points){
      if(p.date().isBefore(start)||p.date().isAfter(end))continue;
      if(!p.eligible()||p.close()==null||p.close().signum()<=0||p.source()==null||
          (source!=null&&!source.equals(p.source()))||reference.putIfAbsent(p.date(),p.close())!=null)
        return unavailable("UNAVAILABLE_BENCHMARK_QUALITY",0,start,end);
      source=p.source();
    }
    List<Double> portfolio=new ArrayList<>(),index=new ArrayList<>();
    for(int i=0;i<13;i++){
      LocalDate a=start.plusWeeks(i),b=a.plusWeeks(1);
      var sample=window.stream().filter(o->!o.date().isBefore(a)&&!o.date().isAfter(b)).toList();
      if(sample.isEmpty()||!sample.getFirst().date().equals(a)||!sample.getLast().date().equals(b))
        return unavailable("UNAVAILABLE_EXACT_WEEKLY_HISTORY",i,start,end);
      if(!reference.containsKey(a)||!reference.containsKey(b))
        return unavailable("UNAVAILABLE_EXACT_BENCHMARK_ANCHORS",i,start,end);
      var result=calculate(sample,flows);
      if(!"AVAILABLE_ESTIMATE".equals(result.status()))return unavailable(result.status(),i,start,end);
      portfolio.add(result.returnPercent()/100.0);
      index.add(reference.get(b).divide(reference.get(a),MathContext.DECIMAL128).subtract(BigDecimal.ONE).doubleValue());
    }
    double pMean=portfolio.stream().mapToDouble(Double::doubleValue).average().orElseThrow();
    double iMean=index.stream().mapToDouble(Double::doubleValue).average().orElseThrow();
    double variance=0,covariance=0,activeVariance=0,wealth=1;
    for(int j=0;j<13;j++){
      double p=portfolio.get(j),b=index.get(j);
      variance+=(b-iMean)*(b-iMean);
      covariance+=(p-pMean)*(b-iMean);
      activeVariance+=Math.pow(p-b-(pMean-iMean),2);
      wealth*=1+p;
    }
    double ret=(wealth-1)*100;
    double benchmark=reference.get(end).divide(reference.get(start),MathContext.DECIMAL128).subtract(BigDecimal.ONE).movePointRight(2).doubleValue();
    double gap=ret-benchmark,te=Math.sqrt(52*activeVariance/12);
    if(!Double.isFinite(ret)||!Double.isFinite(benchmark)||!Double.isFinite(gap)||!Double.isFinite(te))
      return unavailable("UNAVAILABLE_NUMERIC_RANGE",13,start,end);
    Double beta=variance>1e-20?finite(covariance/variance):null;
    Double ir=te>1e-10?finite(52*(pMean-iMean)/te):null;
    return new Assessment("AVAILABLE_PRICE_REFERENCE_ESTIMATE",13,start.toString(),end.toString(),
      ret,benchmark,gap,beta,te*100,ir,gap<=REVIEW_GAP_PP?"REVIEW_RELATIVE_LAG":"NO_RELATIVE_LAG_FLAG");
  }
  private static Double finite(double value){return Double.isFinite(value)?value:null;}
}
