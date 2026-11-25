package com.trading.market;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.*;
import static com.trading.market.PortfolioFlowAdjustedPerformance.*;

/** Recorded portfolio estimates for exact trailing periods, never interpolated. */
public final class PortfolioRollingPerformance {
  private PortfolioRollingPerformance(){}
  public record BenchmarkPoint(LocalDate date,BigDecimal close,String source,boolean eligible){}
  public record Window(int days,String status,String from,String through,Double returnPercent,
      Double drawdownPercent,String benchmarkStatus,Double benchmarkReturnPercent,Double relativePercentagePoints){}
  public record Risk(String status,int weeklyObservations,Double annualizedVolatilityPercent,
      Double annualizedDownsideDeviationPercent,Double negativeWeekFrequencyPercent,String from,String through){}

  public static List<Window> windows(List<Observation> observations,List<Flow> flows,List<BenchmarkPoint> benchmark){
    List<Window> results=new ArrayList<>();
    for(int days:new int[]{30,90,365}){
      if(observations.isEmpty()){
        results.add(new Window(days,"UNAVAILABLE_REQUIRES_TWO_VALUATIONS",null,null,null,null,"UNAVAILABLE_PORTFOLIO_WINDOW",null,null));
        continue;
      }
      LocalDate end=observations.get(observations.size()-1).date(),start=end.minusDays(days);
      List<Observation> sample=observations.stream().filter(o->!o.date().isBefore(start)).toList();
      if(sample.isEmpty()||!sample.get(0).date().equals(start)){
        results.add(new Window(days,"UNAVAILABLE_EXACT_START_DATE",start.toString(),end.toString(),null,null,"UNAVAILABLE_PORTFOLIO_WINDOW",null,null));
        continue;
      }
      Result result=calculate(sample,flows);
      Double relative=null,reference=null;
      String status="UNAVAILABLE_PORTFOLIO_WINDOW";
      if("AVAILABLE_ESTIMATE".equals(result.status())){
        List<BenchmarkPoint> points=benchmark.stream().filter(p->!p.date().isBefore(start)&&!p.date().isAfter(end)).toList();
        status="UNAVAILABLE_EXACT_BENCHMARK_ENDPOINTS";
        var first=points.stream().filter(p->p.date().equals(start)).toList();
        var last=points.stream().filter(p->p.date().equals(end)).toList();
        if(first.size()==1&&last.size()==1){
          status="UNAVAILABLE_BENCHMARK_QUALITY";
          if(points.stream().allMatch(p->p.eligible()&&p.close()!=null&&p.close().signum()>0&&p.source()!=null)
              &&points.stream().map(BenchmarkPoint::source).distinct().count()==1
              &&points.stream().map(BenchmarkPoint::date).distinct().count()==points.size()){
            double value=last.get(0).close().divide(first.get(0).close(),java.math.MathContext.DECIMAL128).subtract(BigDecimal.ONE).movePointRight(2).doubleValue();
            double diff=result.returnPercent()-value;
            if(Double.isFinite(value)&&Double.isFinite(diff)){reference=value;relative=diff;status="AVAILABLE_PRICE_REFERENCE";}
          }
        }
      }
      results.add(new Window(days,result.status(),result.from(),result.through(),result.returnPercent(),result.drawdownPercent(),status,reference,relative));
    }
    return results;
  }

  /** Thirteen consecutive seven-calendar-day linked estimates using exact anchors.
   * Weekly risk is descriptive, not a forecast; no assumed risk-free rate.
   */
  public static Risk risk(List<Observation> observations,List<Flow> flows){
    if(observations.isEmpty())return new Risk("UNAVAILABLE_EXACT_WEEKLY_HISTORY",0,null,null,null,null,null);
    LocalDate end=observations.get(observations.size()-1).date(),start=end.minusWeeks(13);
    List<Double> weekly=new ArrayList<>();
    for(int i=0;i<13;i++){
      LocalDate a=start.plusWeeks(i),b=a.plusWeeks(1);
      List<Observation> sample=observations.stream().filter(o->!o.date().isBefore(a)&&!o.date().isAfter(b)).toList();
      if(sample.isEmpty()||!sample.get(0).date().equals(a)||!sample.get(sample.size()-1).date().equals(b))
        return new Risk("UNAVAILABLE_EXACT_WEEKLY_HISTORY",weekly.size(),null,null,null,start.toString(),end.toString());
      Result result=calculate(sample,flows);
      if(!"AVAILABLE_ESTIMATE".equals(result.status()))
        return new Risk(result.status(),weekly.size(),null,null,null,start.toString(),end.toString());
      weekly.add(result.returnPercent()/100);
    }
    double mean=weekly.stream().mapToDouble(Double::doubleValue).average().orElseThrow();
    double variance=weekly.stream().mapToDouble(v->Math.pow(v-mean,2)).sum()/12;
    double downside=weekly.stream().mapToDouble(v->Math.pow(Math.min(v,0),2)).sum()/13;
    double vol=Math.sqrt(52*variance)*100,down=Math.sqrt(52*downside)*100;
    if(!Double.isFinite(vol)||!Double.isFinite(down))return new Risk("UNAVAILABLE_NUMERIC_RANGE",13,null,null,null,start.toString(),end.toString());
    return new Risk("AVAILABLE_ESTIMATE",13,vol,down,weekly.stream().filter(v->v<0).count()*100.0/13,start.toString(),end.toString());
  }
}
