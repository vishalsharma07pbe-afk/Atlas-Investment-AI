package com.trading.market;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PortfolioOwnershipChangesTest {
  private final ObjectMapper json=new ObjectMapper();
  private final Instant now=Instant.parse("2026-11-25T10:00:00Z");
  private static final List<String> KEYS=List.of("promoters","fii","other_dii","mutual_funds","retail_and_other");
  private static final int[] JUNE={50,19,10,10,11},SEPT={48,20,11,10,11};
  private Map<String,Object> report(String isin,String day,String previous,int[] latest,int[] before,Instant retrieved){
    List<Map<String,Object>> categories=new ArrayList<>();
    for(int i=0;i<KEYS.size();i++){
      var row=new LinkedHashMap<String,Object>();
      row.put("category",KEYS.get(i));row.put("latest_percent",latest[i]);
      row.put("previous_percent",before==null?null:before[i]);categories.add(row);
    }
    var ownership=new LinkedHashMap<String,Object>();
    ownership.put("status",before==null?"LATEST_QUARTER_ONLY":"COMPARABLE_QUARTERS");
    ownership.put("latest_period",day);ownership.put("previous_period",previous);
    ownership.put("categories",categories);
    var company=Map.of("isin",isin,"retrieved_at",retrieved.toString(),
      "sections",Map.of("shareholding",Map.of("source",Map.of("provider","UPSTOX"))),
      "ownership_research",ownership);
    return Map.of("holdings",List.of(Map.of("id",1,"asset_type","EQUITY","exchange","NSE","isin",isin,
      "thesis_evidence",Map.of("company_evidence",company))));
  }
  private Map<String,Object> apply(Map<String,Object> current,Map<String,Object> prior,Instant at){
    return PortfolioOwnershipChanges.attach(current,json.valueToTree(prior),json,at);
  }
  private Map<?,?> holding(Map<String,Object> r){return (Map<?,?>)((List<?>)r.get("holdings")).getFirst();}
  private Map<String,Object> baseline(){
    return apply(report("INE002A01018","2026-06-30",null,JUNE,null,now),Map.of(),now);
  }
  @Test void detectsOnlyNewMatchedQuarterAndRetainsRecentChanges(){
    var first=baseline();
    assertEquals(0,first.get("ownership_changed_count"));
    var current=report("INE002A01018","2026-09-30","2026-06-30",SEPT,JUNE,now);
    var next=apply(current,first,now.plusSeconds(60));
    assertEquals(1,next.get("ownership_changed_count"));assertEquals(1,next.get("ownership_attention_count"));
    var changes=(List<?>)holding(next).get("ownership_changes");
    assertEquals(3,changes.size());
    assertTrue(changes.toString().contains("promoters"));assertTrue(changes.toString().contains("REVIEW"));
    assertEquals(changes,holding(apply(current,next,now.plusSeconds(120))).get("ownership_changes"));
    var later=now.plus(Duration.ofDays(8));
    assertEquals(0,apply(report("INE002A01018","2026-09-30","2026-06-30",SEPT,JUNE,later),next,later).get("ownership_changed_count"));
  }
  @Test void requiresMatchingPriorIdentityAndFreshEvidence(){
    var first=baseline();
    int[] revised={51,18,10,10,11};
    var mismatch=report("INE002A01018","2026-09-30","2026-06-30",SEPT,revised,now);
    assertEquals(0,apply(mismatch,first,now.plusSeconds(60)).get("ownership_changed_count"));
    var other=report("INE009A01021","2026-09-30","2026-06-30",SEPT,JUNE,now);
    assertEquals(0,apply(other,first,now.plusSeconds(60)).get("ownership_changed_count"));
    var stale=report("INE002A01018","2026-09-30","2026-06-30",SEPT,JUNE,now.minus(Duration.ofHours(25)));
    assertEquals("NO_CURRENT_COMPLETE_OWNERSHIP",holding(apply(stale,first,now)).get("ownership_monitor_status"));
    var correction=report("INE002A01018","2026-06-30",null,revised,null,now);
    assertEquals("SAME_QUARTER_REVISION_UNVERIFIED",holding(apply(correction,first,now)).get("ownership_monitor_status"));
  }
  @Test void missingEvidencePreservesBaselineButHidesChanges(){
    var first=baseline();
    var missing=Map.<String,Object>of("holdings",List.of(Map.of("id",1,"asset_type","EQUITY","exchange","NSE","isin","INE002A01018")));
    var unavailable=apply(missing,first,now.plusSeconds(30));
    var current=report("INE002A01018","2026-09-30","2026-06-30",SEPT,JUNE,now);
    var next=apply(current,unavailable,now.plusSeconds(60));
    assertEquals(1,next.get("ownership_attention_count"));
    assertEquals(0,apply(missing,next,now.plusSeconds(120)).get("ownership_changed_count"));
  }
}
