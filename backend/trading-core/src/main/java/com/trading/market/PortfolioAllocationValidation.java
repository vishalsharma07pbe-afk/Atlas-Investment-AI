package com.trading.market;

import java.util.*;

/** Chronological holdout of a fixed candidate family, conditional on today's holdings. */
final class PortfolioAllocationValidation {
  private PortfolioAllocationValidation(){}
  private static final List<String> KINDS=List.of("CURRENT_WEIGHTS","HALFWAY_TO_EQUAL","EQUAL_WEIGHTS");
  private static final double EPS=1e-9;
  record Metric(String kind,double selectionVolatilityPercent,double holdoutVolatilityPercent,
      double holdoutMeanPercent){}
  static Map<String,Object> assess(double[] current,double[][] observations,List<PortfolioEquityCorrelation.Interval> dates){
    var out=new LinkedHashMap<String,Object>();
    out.put("notice","Chronological holdout conditional on today's recorded holdings and weights, not a point-in-time backtest. Candidate selected only by earlier sample volatility and frozen for later observations. Per-interval statistics, no annualization, execution costs, or future performance claim.");
    out.put("metrics",List.of());
    // Fixed split, no tuning on the holdout. At least 30 selection and 15 later observations.
    int n=observations.length,split=(int)Math.floor(n*2.0/3.0);
    if(split<30||n-split<15){
      out.put("status","INSUFFICIENT_HOLDOUT_HISTORY");return out;
    }
    List<Metric> metrics=new ArrayList<>();
    for(int i=0;i<KINDS.size();i++){
      double blend=i/2.0;
      double[] returns=new double[n];
      for(int k=0;k<n;k++)for(int j=0;j<current.length;j++)
        returns[k]+=(current[j]*(1-blend)+blend/current.length)*observations[k][j];
      double selection=volatility(returns,0,split);
      double holdout=volatility(returns,split,n);
      double mean=mean(returns,split,n)*100;
      if(!Double.isFinite(selection)||!Double.isFinite(holdout)||!Double.isFinite(mean)){
        out.put("status","INVALID_HOLDOUT_STATISTICS");return out;
      }
      metrics.add(new Metric(KINDS.get(i),selection,holdout,mean));
    }
    // Deterministic conservative tie handling: current, partial, equal.
    Metric selected=metrics.getFirst();
    for(Metric m:metrics)if(m.selectionVolatilityPercent()<selected.selectionVolatilityPercent()-EPS)selected=m;
    Metric baseline=metrics.getFirst();
    double delta=selected.holdoutVolatilityPercent()-baseline.holdoutVolatilityPercent();
    out.put("status","CONDITIONAL_HOLDOUT_AVAILABLE");
    out.put("selection_count",split);out.put("holdout_count",n-split);
    out.put("selection_from",dates.getFirst().start().toString());
    out.put("selection_through",dates.get(split-1).end().toString());
    out.put("holdout_from",dates.get(split).start().toString());
    out.put("holdout_through",dates.getLast().end().toString());
    out.put("selected_kind",selected.kind());out.put("holdout_volatility_difference_pp",delta);
    out.put("comparison",selected.kind().equals(KINDS.getFirst())?"BASELINE_SELECTED":
      delta < -EPS?"LOWER_OBSERVED_HOLDOUT_VARIABILITY":delta>EPS?"HIGHER_OBSERVED_HOLDOUT_VARIABILITY":"SIMILAR_OBSERVED_HOLDOUT_VARIABILITY");
    out.put("metrics",metrics);
    return out;
  }
  private static double mean(double[] values,int start,int end){
    double sum=0;for(int i=start;i<end;i++)sum+=values[i];return sum/(end-start);
  }
  private static double volatility(double[] values,int start,int end){
    double mean=mean(values,start,end),sum=0;
    for(int i=start;i<end;i++){double d=values[i]-mean;sum+=d*d;}
    return Math.sqrt(sum/(end-start-1))*100;
  }
}
