package com.trading.market;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Instant;
import java.time.Duration;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PortfolioThesisChangesTest {
  private final ObjectMapper json=new ObjectMapper();
  private final Instant now=Instant.parse("2026-11-25T10:00:00Z");
  private Map<String,Object> report(String isin,int year,int previous,int latest,boolean stale){
    var trend=Map.of("metric","NET_PROFIT","previous_year",year-1,"latest_year",year,
      "previous_value",previous,"latest_value",latest,"latest_period","March "+year,"unit","crore",
      "latest_period_may_be_stale",stale);
    var holding=Map.of("id",1,"asset_type","EQUITY","exchange","NSE","isin",isin,
      "thesis_evidence",Map.of("company_evidence",Map.of("financial_trends",Map.of("items",List.of(trend)))));
    return Map.of("holdings",List.of(holding));
  }
  private Map<?,?> holding(Map<String,Object> report){return (Map<?,?>)((List<?>)report.get("holdings")).getFirst();}
  @Test void recordsConsecutiveDirectionChangeAndRetainsItAcrossRefreshes(){
    var first=PortfolioThesisChanges.attach(report("INE002A01018",2025,100,120,false),json.createObjectNode(),json,now);
    assertEquals(0,first.get("thesis_changed_count"));
    var next=PortfolioThesisChanges.attach(report("INE002A01018",2026,120,90,false),json.valueToTree(first),json,now.plusSeconds(60));
    assertEquals(1,next.get("thesis_changed_count"));
    assertEquals("NEW_REPORTED_DIRECTION_CHANGE",holding(next).get("thesis_monitor_status"));
    assertTrue(holding(next).get("thesis_changes").toString().contains("DECLINING"));
    var same=PortfolioThesisChanges.attach(report("INE002A01018",2026,120,90,false),json.valueToTree(next),json,now.plusSeconds(120));
    assertEquals("RECENT_REPORTED_DIRECTION_CHANGE",holding(same).get("thesis_monitor_status"));
    var expired=PortfolioThesisChanges.attach(report("INE002A01018",2026,120,90,false),json.valueToTree(same),json,now.plus(Duration.ofDays(8)));
    assertEquals(0,expired.get("thesis_changed_count"));
  }
  @Test void staleEvidenceDoesNotCreateRecoveryAndIdentityChangesResetBaseline(){
    var first=PortfolioThesisChanges.attach(report("INE002A01018",2025,120,100,false),json.createObjectNode(),json,now);
    var missing=PortfolioThesisChanges.attach(report("INE002A01018",2026,100,150,true),json.valueToTree(first),json,now.plusSeconds(60));
    assertEquals("NO_CURRENT_DATED_TRENDS",holding(missing).get("thesis_monitor_status"));
    assertEquals(0,missing.get("thesis_changed_count"));
    var restored=PortfolioThesisChanges.attach(report("INE002A01018",2026,100,150,false),json.valueToTree(missing),json,now.plusSeconds(120));
    assertEquals(1,restored.get("thesis_changed_count"));
    var other=PortfolioThesisChanges.attach(report("INE009A01021",2026,100,150,false),json.valueToTree(first),json,now.plusSeconds(120));
    assertEquals(0,other.get("thesis_changed_count"));
    var skipped=PortfolioThesisChanges.attach(report("INE002A01018",2027,100,150,false),json.valueToTree(first),json,now.plusSeconds(120));
    assertEquals(0,skipped.get("thesis_changed_count"));
  }
}
