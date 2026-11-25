package com.trading.market;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.*;

/** Same-sample, fixed-weight direct-equity alternatives; not a return forecast. */
final class PortfolioHistoricalAllocation {
  private PortfolioHistoricalAllocation(){}
  record Weight(String isin,String symbol,double weightPercent){}
  record Alternative(String kind,double sampleMeanPercent,double sampleVolatilityPercent,
    double largestWeightPercent,double oneWayTurnoverPercent,List<Weight> weights){}
  static Map<String,Object> assess(Map<String,BigDecimal> values,Map<String,String> symbols,
      Map<String,Map<PortfolioEquityCorrelation.Interval,Double>> series,LocalDate today,boolean complete){
    var out=new LinkedHashMap<String,Object>();
    out.put("notice","Historical fixed-weight direct-equity sleeve comparisons only. Each alternative uses the same matched observed return intervals and sample standard deviation per interval, not annualized volatility or forecast return. Assumes frictionless constant weights across the historical sample. Mutual funds, cash, taxes, fees and trading constraints are excluded. Lowest observed variability is in-sample, not an optimal or recommended allocation.");
    out.put("alternatives",List.of());
    int n=values.size();
    if(!complete||n<2||n>12||values.values().stream().anyMatch(v->v==null||v.signum()<=0||!Double.isFinite(v.doubleValue()))){
      out.put("status","INSUFFICIENT_RECENT_EXACT_DIRECT_EQUITY_COVERAGE");return out;
    }
    var ids=values.keySet().stream().sorted().toList();
    if(ids.stream().anyMatch(id->!id.matches("INE[A-Z0-9]{9}")||!series.containsKey(id)||series.get(id).isEmpty())){
      out.put("status","INSUFFICIENT_ADJUSTED_HISTORY");return out;
    }
    var common=new HashSet<>(series.get(ids.getFirst()).keySet());
    for(String id:ids)common.retainAll(series.get(id).keySet());
    var dates=common.stream().sorted(Comparator.comparing(PortfolioEquityCorrelation.Interval::end)
      .thenComparing(PortfolioEquityCorrelation.Interval::start)).toList();
    if(dates.size()<30||dates.getLast().end().isBefore(today.minusDays(5))){
      out.put("status","INSUFFICIENT_COMMON_RETURN_INTERVALS");return out;
    }
    // Require non-overlapping consecutive common observations. Gaps may be
    // weekends or holidays; no daily annualization is inferred.
    for(int k=0;k<dates.size();k++){
      var d=dates.get(k);
      if(d.start().isBefore(today.minusDays(90))||!d.start().isBefore(d.end())||!d.end().isBefore(today)||
          (k>0&&d.start().isBefore(dates.get(k-1).end()))){
        out.put("status","INVALID_COMMON_RETURN_INTERVALS");return out;
      }
    }
    double total=values.values().stream().mapToDouble(BigDecimal::doubleValue).sum();
    if(!Double.isFinite(total)||total<=0){out.put("status","INVALID_RECORDED_VALUE");return out;}
    double[] current=new double[n];
    double[][] observations=new double[dates.size()][n];
    for(int j=0;j<n;j++){
      String id=ids.get(j);current[j]=values.get(id).doubleValue()/total;
      for(int k=0;k<dates.size();k++){
        Double v=series.get(id).get(dates.get(k));
        if(v==null||!Double.isFinite(v)||v<=-1){out.put("status","INVALID_ADJUSTED_RETURNS");return out;}
        observations[k][j]=v;
      }
    }
    List<Alternative> alternatives=new ArrayList<>();
    for(int step=0;step<=2;step++){
      double blend=step/2.0;
      double[] w=new double[n];
      List<Weight> weights=new ArrayList<>();
      double turnover=0,largest=0;
      for(int j=0;j<n;j++){
        w[j]=current[j]*(1-blend)+blend/n;
        turnover+=Math.abs(w[j]-current[j]);largest=Math.max(largest,w[j]);
        weights.add(new Weight(ids.get(j),symbols.getOrDefault(ids.get(j),ids.get(j)),w[j]*100));
      }
      double[] returns=new double[dates.size()];
      for(int k=0;k<dates.size();k++)for(int j=0;j<n;j++)returns[k]+=w[j]*observations[k][j];
      double mean=Arrays.stream(returns).average().orElseThrow();
      double variance=Arrays.stream(returns).map(v->(v-mean)*(v-mean)).sum()/(returns.length-1);
      double volatility=Math.sqrt(variance)*100;
      if(!Double.isFinite(mean*100)||!Double.isFinite(volatility)){
        out.put("status","INVALID_ADJUSTED_RETURNS");return out;
      }
      alternatives.add(new Alternative(List.of("CURRENT_WEIGHTS","HALFWAY_TO_EQUAL","EQUAL_WEIGHTS").get(step),
        mean*100,volatility,largest*100,turnover*50,weights));
    }
    var lowest=alternatives.stream().min(Comparator.comparingDouble(Alternative::sampleVolatilityPercent)).orElseThrow();
    out.put("status","HISTORICAL_COMPARISON_AVAILABLE");out.put("observations",dates.size());
    out.put("first_date",dates.getFirst().start().toString());out.put("last_date",dates.getLast().end().toString());
    out.put("direct_equity_value",values.values().stream().reduce(BigDecimal.ZERO,BigDecimal::add));
    out.put("lowest_observed_variability",lowest.kind());out.put("alternatives",alternatives);
    return out;
  }
}
