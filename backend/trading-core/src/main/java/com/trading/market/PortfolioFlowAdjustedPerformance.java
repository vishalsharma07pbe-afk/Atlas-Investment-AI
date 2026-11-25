package com.trading.market;

import java.math.BigDecimal;
import java.math.MathContext;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.*;

/** Linked Modified Dietz estimates from recorded holdings-only valuations.
 * Cash flows are signed from the portfolio perspective: contributions positive.
 * Same-day flows at an interval's end are assumed to occur after investment returns.
 * No inferred transactions, interpolated prices or certified time-weighted returns.
 */
public final class PortfolioFlowAdjustedPerformance {
  private static final MathContext MC=MathContext.DECIMAL128;
  public static final int MAX_INTERVAL_DAYS=7;
  private PortfolioFlowAdjustedPerformance(){}
  public record Observation(LocalDate date,BigDecimal value,boolean complete){}
  public record Flow(LocalDate date,BigDecimal amount){}
  public record Result(String status,Double returnPercent,Double drawdownPercent,
                       int intervals,int flowCount,Long maximumIntervalDays,String from,String through){}

  public static Result calculate(List<Observation> observations,List<Flow> flows){
    int intervals=Math.max(0,observations.size()-1),flowCount=0;
    if(intervals==0)return new Result("UNAVAILABLE_REQUIRES_TWO_VALUATIONS",null,null,intervals,0,null,null,null);
    LocalDate first=observations.get(0).date(),last=observations.get(observations.size()-1).date();
    String from=first.toString(),through=last.toString();
    NavigableMap<LocalDate,BigDecimal> daily=new TreeMap<>();
    for(Flow flow:flows){
      if(flow.date().isAfter(first)&&!flow.date().isAfter(last)){
        daily.merge(flow.date(),flow.amount(),BigDecimal::add);flowCount++;
      }
    }
    long largest=0;
    for(int i=1;i<observations.size();i++){
      long days=ChronoUnit.DAYS.between(observations.get(i-1).date(),observations.get(i).date());
      if(days<=0)return new Result("UNAVAILABLE_INVALID_VALUATION_ORDER",null,null,intervals,flowCount,null,from,through);
      largest=Math.max(largest,days);
    }
    for(Observation obs:observations){
      if(!obs.complete()||obs.value()==null||obs.value().signum()<0)
        return new Result("UNAVAILABLE_INCOMPLETE_VALUATIONS",null,null,intervals,flowCount,largest,from,through);
    }
    if(largest>MAX_INTERVAL_DAYS)
      return new Result("UNAVAILABLE_VALUATION_GAPS",null,null,intervals,flowCount,largest,from,through);
    BigDecimal index=BigDecimal.ONE,peak=BigDecimal.ONE,drawdown=BigDecimal.ZERO;
    for(int i=1;i<observations.size();i++){
      Observation start=observations.get(i-1),end=observations.get(i);
      long days=ChronoUnit.DAYS.between(start.date(),end.date());
      BigDecimal net=BigDecimal.ZERO,weighted=BigDecimal.ZERO;
      for(var entry:daily.subMap(start.date(),false,end.date(),true).entrySet()){
        BigDecimal amount=entry.getValue();
        long remaining=ChronoUnit.DAYS.between(entry.getKey(),end.date());
        net=net.add(amount,MC);
        weighted=weighted.add(amount.multiply(BigDecimal.valueOf(remaining),MC)
          .divide(BigDecimal.valueOf(days),MC),MC);
      }
      BigDecimal base=start.value().add(weighted,MC);
      if(start.value().signum()<=0||base.signum()<=0||index.signum()==0)
        return new Result("UNAVAILABLE_NONPOSITIVE_CAPITAL_BASE",null,null,intervals,flowCount,largest,from,through);
      BigDecimal change=end.value().subtract(start.value(),MC).subtract(net,MC);
      BigDecimal factor=BigDecimal.ONE.add(change.divide(base,MC),MC);
      if(factor.signum()<0)
        return new Result("UNAVAILABLE_INCONSISTENT_CASH_FLOWS",null,null,intervals,flowCount,largest,from,through);
      index=index.multiply(factor,MC);
      peak=peak.max(index);
      drawdown=drawdown.min(index.divide(peak,MC).subtract(BigDecimal.ONE,MC));
    }
    double total=index.subtract(BigDecimal.ONE).multiply(BigDecimal.valueOf(100)).doubleValue();
    double maxLoss=drawdown.multiply(BigDecimal.valueOf(100)).doubleValue();
    if(!Double.isFinite(total)||!Double.isFinite(maxLoss))
      return new Result("UNAVAILABLE_NUMERIC_RANGE",null,null,intervals,flowCount,largest,from,through);
    return new Result("AVAILABLE_ESTIMATE",total,maxLoss,intervals,flowCount,largest,from,through);
  }
}
