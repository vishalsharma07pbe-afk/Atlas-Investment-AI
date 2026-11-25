package com.trading.market;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PortfolioFundThesisChangesTest {
  private final ObjectMapper json=new ObjectMapper();
  private final Instant now=Instant.parse("2026-11-25T10:00:00Z");
  private Map<String,Object> report(String plan,String date,double ter,String risk,String manager,Instant collected,boolean conflicts){
    Map<String,Object> d=new LinkedHashMap<>();
    d.put("scheme_code","118955");d.put("isin","INF179K01BB2");d.put("plan",plan);
    d.put("source","TIGZIG_AMFI_DERIVED");d.put("collected_at",collected.toString());
    d.put("ter_date",date);d.put("aum_date",date);d.put("document_date",date);
    d.put("ter_percent",ter);d.put("riskometer",risk);d.put("fund_managers",manager);
    d.put("benchmark","Nifty 100 TRI");d.put("exit_load","1% within one year");
    d.put("conflicts",conflicts?List.of("RISKOMETER_CONFLICT"):List.of());
    return Map.of("holdings",List.of(Map.of("id",1,"asset_type","MUTUAL_FUND","exact_scheme_code",118955,
      "fund_thesis_evidence",Map.of("status","SECONDARY_REPORTED_EVIDENCE","disclosure",d))));
  }
  private Map<String,Object> apply(Map<String,Object> current,Map<String,Object> previous,Instant at){
    return PortfolioFundThesisChanges.attach(current,json.valueToTree(previous),json,at);
  }
  private Map<?,?> holding(Map<String,Object> report){return (Map<?,?>)((List<?>)report.get("holdings")).getFirst();}
  @Test void detectsDatedFeeRiskAndManagerChangesAndRetainsThem(){
    var first=apply(report("DIRECT","2026-11-24",0.7,"HIGH","Manager A",now,false),Map.of(),now);
    assertEquals(0,first.get("fund_thesis_changed_count"));
    var current=report("DIRECT","2026-11-25",0.9,"VERY_HIGH","Manager B",now,false);
    var next=apply(current,first,now.plusSeconds(60));
    assertEquals(1,next.get("fund_thesis_changed_count"));
    assertEquals(1,next.get("fund_thesis_attention_count"));
    var changes=(List<?>)holding(next).get("fund_thesis_changes");
    assertEquals(3,changes.size());
    assertTrue(changes.toString().contains("MANAGERS"));
    assertTrue(changes.toString().contains("VERY_HIGH"));
    assertEquals(changes,holding(apply(current,next,now.plusSeconds(120))).get("fund_thesis_changes"));
    var later=report("DIRECT","2026-11-25",0.9,"VERY_HIGH","Manager B",now.plus(Duration.ofDays(8)),false);
    assertEquals(0,apply(later,next,now.plus(Duration.ofDays(8))).get("fund_thesis_changed_count"));
  }
  @Test void missingOrConflictingEvidenceDoesNotInventAChangeAndIdentityResets(){
    var first=apply(report("DIRECT","2026-11-24",0.7,"HIGH","Manager A",now,false),Map.of(),now);
    var missing=Map.<String,Object>of("holdings",List.of(Map.of("id",1,"asset_type","MUTUAL_FUND","exact_scheme_code",118955)));
    var unavailable=apply(missing,first,now.plusSeconds(60));
    assertEquals("NO_CURRENT_DATED_DISCLOSURES",holding(unavailable).get("fund_monitor_status"));
    var sameDate=report("DIRECT","2026-11-24",0.9,"VERY_HIGH","Manager B",now,false);
    assertEquals(0,apply(sameDate,first,now.plusSeconds(60)).get("fund_thesis_changed_count"));
    var conflict=report("DIRECT","2026-11-25",0.7,"VERY_HIGH","Manager A",now,true);
    assertEquals(0,apply(conflict,unavailable,now.plusSeconds(120)).get("fund_thesis_changed_count"));
    var recovered=report("DIRECT","2026-11-25",0.7,"VERY_HIGH","Manager A",now,false);
    assertEquals(1,apply(recovered,unavailable,now.plusSeconds(120)).get("fund_thesis_attention_count"));
    var switched=report("REGULAR","2026-11-25",1.4,"VERY_HIGH","Manager B",now,false);
    assertEquals(0,apply(switched,first,now.plusSeconds(120)).get("fund_thesis_changed_count"));
  }
  @Test void feeReductionAndLowerRiskAreObservationsNotRecoveryVerdicts(){
    var first=apply(report("DIRECT","2026-11-24",0.9,"VERY_HIGH","Manager A",now,false),Map.of(),now);
    var next=apply(report("DIRECT","2026-11-25",0.7,"HIGH","Manager A",now,false),first,now.plusSeconds(60));
    assertEquals(1,next.get("fund_thesis_changed_count"));
    assertEquals(0,next.get("fund_thesis_attention_count"));
  }
}
