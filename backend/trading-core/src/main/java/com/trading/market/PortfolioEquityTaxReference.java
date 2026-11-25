package com.trading.market;

import java.math.*;
import java.time.LocalDate;
import java.util.*;

/** Conditional reference arithmetic, not determination of an assessee's tax. */
final class PortfolioEquityTaxReference {
  private PortfolioEquityTaxReference(){}
  private static final BigDecimal ZERO=BigDecimal.ZERO;
  private static final BigDecimal SHORT_RATE=new BigDecimal("0.20"),LONG_RATE=new BigDecimal("0.125");
  private static final BigDecimal ANNUAL_THRESHOLD=new BigDecimal("125000");
  private static final LocalDate FROM=LocalDate.of(2026,4,1),THROUGH=LocalDate.of(2027,3,31);
  record ConsumedLot(String asset,String exchange,LocalDate acquired,BigDecimal gain){}
  record Reference(String status,String taxYear,BigDecimal shortPositiveGains,BigDecimal shortGrossLosses,
      BigDecimal longPositiveGains,BigDecimal longGrossLosses,BigDecimal baseTaxIfFullThresholdUnused,
      BigDecimal baseTaxIfThresholdAlreadyUsed,List<String> withheld){}
  static Reference assess(List<ConsumedLot> lots,LocalDate today){
    if(lots.isEmpty())return withheld("NO_HYPOTHETICAL_SALE",List.of());
    if(today.isBefore(FROM)||today.isAfter(THROUGH))
      return withheld("RULE_YEAR_NOT_VERIFIED",List.of("Rules are pinned to tax year 2026-27; refresh legal evidence before use in another year."));
    var blockers=new TreeSet<String>();
    BigDecimal shortGain=ZERO,shortLoss=ZERO,longGain=ZERO,longLoss=ZERO;
    for(var lot:lots){
      if(!"EQUITY".equals(lot.asset())||!Set.of("NSE","BSE").contains(lot.exchange())){
        blockers.add("Only listed Indian equity sale lots are supported; fund tax status is not established.");continue;
      }
      if(lot.acquired()==null||lot.acquired().isAfter(today)||!lot.acquired().isAfter(LocalDate.of(2018,1,31))){
        blockers.add("Acquisition date unsupported or requires grandfathered cost evidence.");continue;
      }
      if(lot.gain()==null){blockers.add("Missing lot gain evidence.");continue;}
      boolean longTerm=today.isAfter(lot.acquired().plusMonths(12));
      if(longTerm){
        if(lot.gain().signum()>=0)longGain=longGain.add(lot.gain());else longLoss=longLoss.add(lot.gain().negate());
      }else{
        if(lot.gain().signum()>=0)shortGain=shortGain.add(lot.gain());else shortLoss=shortLoss.add(lot.gain().negate());
      }
    }
    if(!blockers.isEmpty())return withheld("INSUFFICIENT_RULE_SCOPE",List.copyOf(blockers));
    BigDecimal shortTax=shortGain.multiply(SHORT_RATE);
    return new Reference("CONDITIONAL_REFERENCE_ONLY","2026-27",money(shortGain),money(shortLoss),money(longGain),money(longLoss),
      money(shortTax.add(longGain.subtract(ANNUAL_THRESHOLD).max(ZERO).multiply(LONG_RATE))),
      money(shortTax.add(longGain.multiply(LONG_RATE))),List.of());
  }
  static Reference withheld(String status,List<String> reasons){
    return new Reference(status,"2026-27",null,null,null,null,null,null,reasons);
  }
  private static BigDecimal money(BigDecimal n){return n.setScale(2,RoundingMode.HALF_UP);}
}
