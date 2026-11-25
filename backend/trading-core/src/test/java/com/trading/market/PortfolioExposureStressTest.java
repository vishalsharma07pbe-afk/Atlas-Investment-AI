package com.trading.market;

import java.math.BigDecimal;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PortfolioExposureStressTest {
  private static BigDecimal amount(String value){return new BigDecimal(value);}
  private static List<PortfolioExposureStress.Exposure> identities(){
    return List.of(new PortfolioExposureStress.Exposure("ISIN:INE002A01018","A",amount("400")),
      new PortfolioExposureStress.Exposure("ISIN:INE009A01021","B",amount("200")),
      new PortfolioExposureStress.Exposure("AMFI:123456","123456",amount("400")));
  }
  private Map<String,Object> assess(boolean recent,boolean exact,boolean sectors){
    return PortfolioExposureStress.assess(amount("1000"),Map.of("EQUITY",amount("600"),"MUTUAL_FUND",amount("400")),
      identities(),sectors?Map.of("energy",amount("400"),"finance",amount("200")):Map.of("Unknown",amount("600")),
      recent,exact,sectors);
  }
  private PortfolioExposureStress.Scenario scenario(Map<String,Object> report,String kind){
    return ((List<?>)report.get("scenarios")).stream().map(PortfolioExposureStress.Scenario.class::cast)
      .filter(s->kind.equals(s.kind())).findFirst().orElseThrow();
  }
  private void equal(String value,BigDecimal actual){assertEquals(0,amount(value).compareTo(actual));}
  @Test void mixedPortfolioShockImpactsDoNotDoubleCountFundExposure(){
    var report=assess(true,true,true);
    assertEquals("HYPOTHETICAL_SCENARIOS_AVAILABLE",report.get("status"));
    assertEquals(5,((List<?>)report.get("scenarios")).size());
    equal("-120",scenario(report,"DIRECT_EQUITY_SELL_OFF").changeAmount());
    equal("-40",scenario(report,"FUND_NAV_DECLINE").changeAmount());
    var combined=scenario(report,"COMBINED_DOWNSIDE");
    equal("-160",combined.changeAmount());equal("-16",combined.changePercent());equal("840",combined.stressedValue());
    var identity=scenario(report,"LARGEST_IDENTITY_SHOCK");
    equal("-120",identity.changeAmount());
    var sector=scenario(report,"LARGEST_DIRECT_SECTOR_SHOCK");
    equal("-100",sector.changeAmount());equal("900",sector.stressedValue());
  }
  @Test void missingIdentityAndSectorSuppressOnlyDependentScenarios(){
    var report=assess(true,false,false);
    assertEquals("PARTIAL_SCENARIO_COVERAGE",report.get("status"));
    assertEquals(3,((List<?>)report.get("scenarios")).size());
    assertEquals(2,((List<?>)report.get("withheld")).size());
  }
  @Test void incompleteValuationsOrUnreconciledAssetsSuppressAllScenarios(){
    assertEquals("INSUFFICIENT_RECENT_VALUATIONS",assess(false,true,true).get("status"));
    assertEquals(List.of(),assess(false,true,true).get("scenarios"));
    var bad=PortfolioExposureStress.assess(amount("1000"),Map.of("EQUITY",amount("900")),identities(),
      Map.of(),true,true,false);
    assertEquals("INSUFFICIENT_RECENT_VALUATIONS",bad.get("status"));
  }
  @Test void fundOnlyPortfolioDoesNotInventEquityOrSectorScenarios(){
    var report=PortfolioExposureStress.assess(amount("500"),Map.of("MUTUAL_FUND",amount("500")),
      List.of(new PortfolioExposureStress.Exposure("AMFI:123456","123456",amount("500"))),
      Map.of(),true,true,true);
    assertEquals("HYPOTHETICAL_SCENARIOS_AVAILABLE",report.get("status"));
    assertEquals(2,((List<?>)report.get("scenarios")).size());
    equal("450",scenario(report,"FUND_NAV_DECLINE").stressedValue());
  }
}
