package com.trading.market;
import java.time.LocalDate;
import java.util.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
class PortfolioReassessmentTest {
 private final ObjectMapper json=new ObjectMapper();
 @Test void incompleteInputsNeverCreateScoreAndAttentionWins(){
  var h=Map.<String,Object>of("asset_type","EQUITY","status","REVIEW_REQUIRED");
  var result=PortfolioReassessment.holding(h,json,LocalDate.of(2026,11,27));
  assertNull(result.get("score"));assertEquals("REASSESS_EVIDENCE",result.get("review_state"));
  assertEquals(false,result.get("qualified"));
 }
 @Test void completeExactEquityFundHistoryScoresButNeverQualifies(){
  var weekly=Map.of("methodology","MF-WEEKLY-MATCH-1","anchor_count",157,"last_date","2026-11-26","date_digest","a".repeat(64),"cagr_percent",12,"drawdown_percent",-20);
  var history=Map.of("scheme_code",123456,"isin_growth","INF179K01BB2","amfi_option","GROWTH","category","Open Ended Schemes(Equity Scheme - Large Cap Fund)","matched_weekly_comparison",weekly,"worst_rolling_52w_annualized_percent",2,"weekly_volatility_percent",18);
  var row=new LinkedHashMap<String,Object>();row.put("asset_type","MUTUAL_FUND");row.put("exact_scheme_code",123456);row.put("fund_history_evidence",history);
  var result=PortfolioReassessment.holding(row,json,LocalDate.of(2026,11,27));
  assertNotNull(result.get("score"));assertEquals("MONITOR_RESEARCH_ONLY",result.get("review_state"));
  row.put("reassessment",result);
  assertEquals(1,PortfolioReassessment.synthesis(List.of(row),json).get("scored_count"));
  row.put("exact_scheme_code",654321);assertNull(PortfolioReassessment.holding(row,json,LocalDate.of(2026,11,27)).get("score"));
 }
}
