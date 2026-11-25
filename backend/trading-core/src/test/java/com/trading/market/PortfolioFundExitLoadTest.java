package com.trading.market;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.math.BigDecimal;
import java.time.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PortfolioFundExitLoadTest {
  private static final Instant NOW=Instant.parse("2026-11-25T10:00:00Z");
  private static final LocalDate TODAY=LocalDate.of(2026,11,25);
  private static final String CODE="123456";
  private static final String SIMPLE="1% if redeemed on or before 365 days from the date of allotment. Nil thereafter.";
  private final ObjectMapper json=new ObjectMapper();
  private BigDecimal n(String v){return new BigDecimal(v);}
  private PortfolioJournalLots.Holding journal(String code){
    return new PortfolioJournalLots.Holding(code,"MUTUAL_FUND","PROVISIONAL_JOURNAL_RECONCILED",n("10"),n("10"),n("1000"),n("1000"),
      List.of(new PortfolioJournalLots.OpenLot(TODAY.minusDays(366).toString(),n("2"),n("100"),366),
        new PortfolioJournalLots.OpenLot(TODAY.minusDays(365).toString(),n("3"),n("100"),365),
        new PortfolioJournalLots.OpenLot(TODAY.minusDays(30).toString(),n("5"),n("100"),30)));
  }
  private PortfolioSaleResearch.Sale sale(String code){
    return new PortfolioSaleResearch.Sale("AMFI:"+code,code,"MUTUAL_FUND",n("4"),n("800"),n("400"),n("400"),365,366);
  }
  private ObjectNode holding(String code,String terms){
    var h=json.createObjectNode();h.put("asset_type","MUTUAL_FUND");h.put("symbol",code);h.put("exact_scheme_code",Long.parseLong(code));
    var evidence=h.putObject("fund_thesis_evidence");evidence.put("status","SECONDARY_REPORTED_EVIDENCE");
    var d=evidence.putObject("disclosure");d.put("status","SECONDARY_REPORTED_NOT_INDEPENDENTLY_VERIFIED")
      .put("source","TIGZIG_AMFI_DERIVED").put("scheme_code",code).put("isin","INF000A01018").put("plan","DIRECT")
      .put("collected_at",NOW.toString()).put("document_date","2026-10-31").put("exit_load",terms);
    d.putArray("conflicts");return h;
  }
  private void equal(String expected,BigDecimal actual){assertEquals(0,n(expected).compareTo(actual));}
  @Test void partialFifoRedemptionChargesOnlyUnitsWithinExplicitInclusiveDayBoundary(){
    var result=PortfolioFundExitLoad.estimate(sale(CODE),journal(CODE),holding(CODE,SIMPLE),NOW);
    assertEquals("CONDITIONAL_CURRENT_TERMS",result.status());
    equal("4",result.hypotheticalLoad());equal("796",result.proceedsAfterLoad());
    assertEquals("2026-10-31",result.disclosureDate());
  }
  @Test void nilIsExplicitAndComplexTermsAreNotGuessed(){
    var nil=PortfolioFundExitLoad.estimate(sale(CODE),journal(CODE),holding(CODE,"Nil"),NOW);
    equal("0",nil.hypotheticalLoad());
    for(String terms:List.of("1% within one year","1% if redeemed within 365 days. Nil thereafter.",
        "Nil for first 10% of units; 1% thereafter",SIMPLE+" Except SIP units.","")){
      var result=PortfolioFundExitLoad.estimate(sale(CODE),journal(CODE),holding(CODE,terms),NOW);
      assertEquals("EXIT_LOAD_WITHHELD",result.status());assertNull(result.hypotheticalLoad());
    }
  }
  @Test void staleFutureConflictingOrUnmatchedDisclosuresAreWithheld(){
    for(String field:List.of("collected_at","document_date","scheme_code")){
      var h=holding(CODE,SIMPLE);
      var d=(ObjectNode)h.path("fund_thesis_evidence").path("disclosure");
      d.put(field, switch(field){
        case "collected_at" -> NOW.minus(Duration.ofDays(4)).toString();
        case "document_date" -> "2026-12-01";
        default -> "654321";
      });
      assertNull(PortfolioFundExitLoad.estimate(sale(CODE),journal(CODE),h,NOW).hypotheticalLoad());
    }
    var h=holding(CODE,SIMPLE);
    ((ObjectNode)h.path("fund_thesis_evidence").path("disclosure")).putArray("conflicts").add("EXIT_LOAD_CONFLICT");
    assertNull(PortfolioFundExitLoad.estimate(sale(CODE),journal(CODE),h,NOW).hypotheticalLoad());
  }
  @Test void oneUnsupportedFundWithholdsScenarioTotalButPreservesOtherFundEvidence(){
    String second="654321";
    var scenario=new PortfolioSaleResearch.Scenario("MIXED_ALLOCATION","EQUAL_WEIGHTS","PROVISIONAL_SALE_EVIDENCE",
      n("1600"),n("800"),n("800"),List.of(sale(CODE),sale(second)),List.of(),
      PortfolioEquityTaxReference.withheld("INSUFFICIENT_RULE_SCOPE",List.of()));
    var report=Map.<String,Object>of("sale_research",Map.of("scenarios",List.of(scenario)),
      "journal_lot_reconciliation",Map.of("holdings",List.of(journal(CODE),journal(second))),
      "holdings",List.of(holding(CODE,SIMPLE),holding(second,"Unknown")));
    var result=PortfolioFundExitLoad.assess(report,json,NOW);
    var row=(PortfolioFundExitLoad.Scenario)((List<?>)result.get("scenarios")).getFirst();
    assertEquals("INCOMPLETE_EXIT_LOAD_EVIDENCE",row.status());assertNull(row.hypotheticalFundExitLoad());
    equal("4",row.funds().getFirst().hypotheticalLoad());assertNull(row.funds().getLast().hypotheticalLoad());
  }
}
