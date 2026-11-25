package com.trading.market;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.*;

/** Separate, illustrative exposure shocks; no probabilities or market forecasts. */
final class PortfolioExposureStress {
  private PortfolioExposureStress(){}
  private static final BigDecimal ZERO=BigDecimal.ZERO,HUNDRED=BigDecimal.valueOf(100);
  record Exposure(String identity,String label,BigDecimal value){}
  record Shock(String exposure,String label,int assumedChangePercent,BigDecimal recordedExposure,BigDecimal valueChange){}
  record Scenario(String kind,String title,List<Shock> shocks,BigDecimal changeAmount,
      BigDecimal changePercent,BigDecimal stressedValue){}
  static Map<String,Object> assess(BigDecimal total,Map<String,BigDecimal> assets,List<Exposure> identities,
      Map<String,BigDecimal> sectors,boolean recent,boolean exact,boolean sectorComplete){
    var out=new LinkedHashMap<String,Object>();
    out.put("notice","Independent, hypothetical instantaneous price/NAV shocks using recent recorded values, not verified live valuations. Unshocked positions are held constant. Direct equity and fund NAV shocks are separate assumptions; fund underlying holdings, correlations, liquidity, fees and taxes are not modeled. Scenarios are neither forecasts nor additive.");
    out.put("scenarios",List.of());
    out.put("withheld",List.of());
    if(!recent||total==null||total.signum()<=0||!Double.isFinite(total.doubleValue())||
        !valid(assets.values())||!assets.keySet().stream().allMatch(Set.of("EQUITY","MUTUAL_FUND")::contains)||
        sum(assets.values()).compareTo(total)!=0){
      out.put("status","INSUFFICIENT_RECENT_VALUATIONS");return out;
    }
    out.put("recorded_value",money(total));
    List<Scenario> scenarios=new ArrayList<>();
    List<String> withheld=new ArrayList<>();
    BigDecimal equity=assets.getOrDefault("EQUITY",ZERO),funds=assets.getOrDefault("MUTUAL_FUND",ZERO);
    if(equity.signum()>0)scenarios.add(scenario("DIRECT_EQUITY_SELL_OFF","Direct equity sell-off",total,
      List.of(shock("DIRECT_EQUITY","Direct equity",-20,equity))));
    if(funds.signum()>0)scenarios.add(scenario("FUND_NAV_DECLINE","Fund NAV decline",total,
      List.of(shock("FUND_NAV","Mutual fund NAV",-10,funds))));
    if(equity.signum()>0&&funds.signum()>0)scenarios.add(scenario("COMBINED_DOWNSIDE","Combined equity and fund NAV decline",total,
      List.of(shock("DIRECT_EQUITY","Direct equity",-20,equity),shock("FUND_NAV","Mutual fund NAV",-10,funds))));
    if(exact&&!identities.isEmpty()&&valid(identities.stream().map(Exposure::value).toList())&&
        identities.stream().map(Exposure::identity).distinct().count()==identities.size()&&
        sum(identities.stream().map(Exposure::value).toList()).compareTo(total)==0){
      var largest=identities.stream().sorted(Comparator.comparing(Exposure::value).reversed().thenComparing(Exposure::identity)).findFirst().orElseThrow();
      scenarios.add(scenario("LARGEST_IDENTITY_SHOCK","Largest investment shock",total,
        List.of(shock("EXACT_IDENTITY",largest.label(),-30,largest.value()))));
    }else withheld.add("LARGEST_IDENTITY_REQUIRES_COMPLETE_EXACT_IDENTITIES");
    if(equity.signum()>0){
      if(sectorComplete&&!sectors.isEmpty()&&!sectors.containsKey("Unknown")&&valid(sectors.values())&&sum(sectors.values()).compareTo(equity)==0){
        var largest=sectors.entrySet().stream().sorted(Map.Entry.<String,BigDecimal>comparingByValue().reversed().thenComparing(Map.Entry.comparingByKey())).findFirst().orElseThrow();
        scenarios.add(scenario("LARGEST_DIRECT_SECTOR_SHOCK","Largest direct-equity sector shock",total,
          List.of(shock("DIRECT_EQUITY_SECTOR",largest.getKey(),-25,largest.getValue()))));
      }else withheld.add("SECTOR_SHOCK_REQUIRES_COMPLETE_DIRECT_EQUITY_CLASSIFICATION");
    }
    out.put("status",withheld.isEmpty()?"HYPOTHETICAL_SCENARIOS_AVAILABLE":"PARTIAL_SCENARIO_COVERAGE");
    out.put("scenarios",scenarios);
    out.put("withheld",withheld);
    return out;
  }
  private static boolean valid(Collection<BigDecimal> values){
    return values.stream().allMatch(v->v!=null&&v.signum()>=0&&Double.isFinite(v.doubleValue()));
  }
  private static BigDecimal sum(Collection<BigDecimal> values){return values.stream().reduce(ZERO,BigDecimal::add);}
  private static BigDecimal money(BigDecimal value){return value.setScale(2,RoundingMode.HALF_UP);}
  private static Shock shock(String exposure,String label,int move,BigDecimal value){
    return new Shock(exposure,label,move,value,value.multiply(BigDecimal.valueOf(move)).movePointLeft(2));
  }
  private static Scenario scenario(String kind,String title,BigDecimal total,List<Shock> shocks){
    BigDecimal change=sum(shocks.stream().map(Shock::valueChange).toList());
    return new Scenario(kind,title,shocks,money(change),change.multiply(HUNDRED).divide(total,2,RoundingMode.HALF_UP),money(total.add(change)));
  }
}
