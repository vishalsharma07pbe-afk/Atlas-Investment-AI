package com.trading.market;

import java.math.BigDecimal;
import java.time.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PortfolioReviewServiceTest {
  @Test void warnsAboutConcentrationLossAndHistoricalDecline(){
    LocalDate date=LocalDate.of(2026,11,24);
    Map<String,Object> row=new HashMap<>();
    row.put("id",1L);row.put("symbol","TEST");row.put("asset_type","EQUITY");
    row.put("instrument_id",5L);row.put("exchange","NSE");
    row.put("market_value",new BigDecimal("80"));row.put("invested",new BigDecimal("100"));
    row.put("history_count",50L);row.put("distinct_dates",50L);row.put("adjustments",1L);
    row.put("evidence_date",date.minusDays(1));row.put("latest",new BigDecimal("80"));
    row.put("prior",new BigDecimal("90"));row.put("peak",new BigDecimal("100"));
    row.put("average_close",new BigDecimal("95"));
    var result=PortfolioReviewService.assess(List.of(row),date,Instant.EPOCH);
    assertEquals(1,result.get("attention_count"));
    assertEquals(0,result.get("data_gap_count"));
    var item=(Map<?,?>)((List<?>)result.get("holdings")).get(0);
    assertEquals("REVIEW_REQUIRED",item.get("status"));
    assertEquals(-20.0,item.get("recorded_return_percent"));
    assertEquals(5,((List<?>)item.get("findings")).size());
  }
  @Test void staleHistoryNeverProducesTechnicalConclusion(){
    LocalDate date=LocalDate.of(2026,11,24);
    var row=Map.<String,Object>of("id",1L,"symbol","123","asset_type","MUTUAL_FUND",
      "history_count",50L,"distinct_sources",1L,"evidence_date",date.minusDays(30),
      "latest",BigDecimal.ONE,"prior",BigDecimal.TEN,"peak",BigDecimal.TEN);
    var result=PortfolioReviewService.assess(List.of(row),date,Instant.EPOCH);
    var item=(Map<?,?>)((List<?>)result.get("holdings")).get(0);
    assertEquals("EVIDENCE_GAP",item.get("status"));
    assertNull(item.get("change_20_observations_percent"));
    assertNull(item.get("recent_peak_change_percent"));
  }
  @Test void positiveCrossVenueRestrictionIsReviewEvidenceEvenWithMissingPrices(){
    LocalDate date=LocalDate.of(2026,11,27);
    var row=new HashMap<String,Object>();
    row.put("id",1L);row.put("symbol","TEST");row.put("asset_type","EQUITY");row.put("exchange","NSE");
    row.put("isin","INE002A01018");row.put("instrument_id",5L);
    row.put("positive_security_observations","BSE SUSPENDED_REPORTED (observed 2026-11-20)");
    var result=PortfolioReviewService.assess(List.of(row),date,Instant.EPOCH);
    var item=(Map<?,?>)((List<?>)result.get("holdings")).getFirst();
    assertEquals("REVIEW_REQUIRED",item.get("status"));
    assertEquals(1,result.get("attention_count"));
    assertTrue(item.get("findings").toString().contains("BSE SUSPENDED_REPORTED (observed 2026-11-20)"));
    assertTrue(item.get("findings").toString().contains("another venue is not automatically restricted"));
    row.remove("positive_security_observations");
    var unknown=PortfolioReviewService.assess(List.of(row),date,Instant.EPOCH);
    var missing=(Map<?,?>)((List<?>)unknown.get("holdings")).getFirst();
    assertEquals("EVIDENCE_GAP",missing.get("status"));
    assertTrue(missing.get("missing_evidence").toString().contains("restriction clearance is not established"));
  }
}
