package com.trading.market;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PortfolioEquityTaxReferenceTest {
  private static final LocalDate TODAY=LocalDate.of(2026,11,25);
  private PortfolioEquityTaxReference.ConsumedLot equity(LocalDate acquired,String gain){
    return new PortfolioEquityTaxReference.ConsumedLot("EQUITY","NSE",acquired,new BigDecimal(gain));
  }
  private void equal(String expected,BigDecimal actual){assertEquals(0,new BigDecimal(expected).compareTo(actual));}
  @Test void annualThresholdAppliedOnceAcrossPositiveLongLotsAndLossesSeparated(){
    var ref=PortfolioEquityTaxReference.assess(List.of(
      equity(TODAY.minusMonths(12),"10000"),
      equity(TODAY.minusMonths(12).minusDays(1),"100000"),
      equity(TODAY.minusMonths(15),"50000"),
      equity(TODAY.minusMonths(2),"-3000"),
      equity(TODAY.minusMonths(16),"-2000")),TODAY);
    assertEquals("CONDITIONAL_REFERENCE_ONLY",ref.status());
    equal("10000",ref.shortPositiveGains());equal("3000",ref.shortGrossLosses());
    equal("150000",ref.longPositiveGains());equal("2000",ref.longGrossLosses());
    equal("5125",ref.baseTaxIfFullThresholdUnused());
    equal("20750",ref.baseTaxIfThresholdAlreadyUsed());
  }
  @Test void unsupportedLotWithholdsWholeScenarioReference(){
    var fund=new PortfolioEquityTaxReference.ConsumedLot("MUTUAL_FUND","",TODAY.minusYears(2),BigDecimal.TEN);
    for(var unsupported:List.of(fund,equity(LocalDate.of(2018,1,31),"1000"),equity(TODAY.plusDays(1),"1000"))){
      var ref=PortfolioEquityTaxReference.assess(List.of(equity(TODAY.minusMonths(3),"100"),unsupported),TODAY);
      assertEquals("INSUFFICIENT_RULE_SCOPE",ref.status());assertNull(ref.baseTaxIfFullThresholdUnused());
    }
  }
  @Test void yearBoundaryAndNoSaleDoNotInventTaxes(){
    var lot=equity(TODAY.minusYears(2),"100");
    for(var day:List.of(LocalDate.of(2026,3,31),LocalDate.of(2027,4,1))){
      var ref=PortfolioEquityTaxReference.assess(List.of(lot),day);
      assertEquals("RULE_YEAR_NOT_VERIFIED",ref.status());assertNull(ref.baseTaxIfThresholdAlreadyUsed());
    }
    assertEquals("NO_HYPOTHETICAL_SALE",PortfolioEquityTaxReference.assess(List.of(),TODAY).status());
  }
}
