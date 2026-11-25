import unittest
from datetime import date
from app import stock_qualification as qualification
from app.horizon_research import VERSION

TODAY=date(2026,11,26)
def fixture():
    item={"id":1,"symbol":"TEST","exchange":"NSE","isin":"INE002A01018","as_of":"2026-11-25",
          "history_count":220,"rank_score":15,"close":100,"atr_percent":2,"adjustment_status":"ADJUSTED",
          "research_conclusion":{"blockers":["EVENT_RISK_NOT_VERIFIED"],"warnings":[]},
          "matched_strategy_replay":{"status":"REPLAY_OBSERVED","as_of":"2026-11-25","trades":40,
              "cost_scenarios":[{"cost_bps_per_side":30,"net_return_percent":5}]},
          "ai_review":{"committee":{"claim_comparison":{"matched_count":5,"contradicted_count":0,"rejected_count":0}}}}
    group={"status":"TECHNICAL_WATCH_ONLY","methodology":VERSION,"candidates":[item],"blockers":[]}
    snapshot={"enabled":True,"sections":[{"section":"NSE","status":"READY","result":{
        "discovery_coverage":{"calendar_status":"PUBLISHED_SESSION","calendar_checked_on":"2026-11-26",
                              "expected_session":"2026-11-25"},
        "horizons":{"SWING":group}}}]}
    return snapshot,item,group

class StockQualificationTests(unittest.TestCase):
    def test_positive_observations_do_not_lift_independent_gates(self):
        snap,item,_=fixture()
        qualification.attach(snap,TODAY)
        report=item["stock_qualification"]
        self.assertEqual(report["status"],"WITHHELD_EVIDENCE_GAPS")
        self.assertEqual(report["gates"][0]["status"],"OBSERVATION_CHECKS_MET")
        self.assertIn("EVENT_RISK_NOT_VERIFIED",report["blockers"])
        self.assertIn("FINAL_QUALIFICATION_VALIDATION_REQUIRED",report["blockers"])
        summary=snap["stock_qualification"]["horizons"]["SWING"]
        self.assertEqual(summary["reviewed_count"],1)
        self.assertEqual(summary["qualified_count"],0)
        self.assertEqual(summary["recommendations"],[])
        self.assertIsNone(snap["stock_qualification"]["horizons"]["INTRADAY"]["qualified_count"])
    def test_conflicts_stale_identity_and_duplicate_count(self):
        snap,item,group=fixture()
        item["isin"]="INVALID"
        item["as_of"]="2026-11-20"
        item["ai_review"]["committee"]["claim_comparison"]["contradicted_count"]=2
        group["candidates"].append(dict(item))
        qualification.attach(snap,TODAY)
        report=item["stock_qualification"]
        self.assertEqual(report["status"],"WITHHELD_REVIEW_REQUIRED")
        self.assertIn("EXACT_STOCK_IDENTITY_REQUIRED",report["blockers"])
        self.assertIn("CURRENT_EXPECTED_SESSION_REQUIRED",report["blockers"])
        self.assertIn("AI_ASSERTIONS_CONTRADICT_SUPPLIED_EVIDENCE",report["review_findings"])
        self.assertEqual(snap["stock_qualification"]["horizons"]["SWING"]["reviewed_count"],1)
    def test_failed_snapshot_does_not_count_as_zero_qualified_market(self):
        snap,item,_=fixture()
        snap["sections"][0]["status"]="FAILED"
        qualification.attach(snap,TODAY)
        self.assertNotIn("stock_qualification",item)
        self.assertIsNone(snap["stock_qualification"]["horizons"]["SWING"]["qualified_count"])

    def test_cross_venue_selection_preserves_all_review_findings(self):
        from copy import deepcopy
        snap,item,group=fixture()
        other=deepcopy(item)
        other.update(exchange="BSE",id=2,rank_score=99)
        other["research_conclusion"]["warnings"]=["REPORTED_REVENUE_DECLINE"]
        result=deepcopy(snap["sections"][0]["result"])
        result["horizons"]["SWING"]["candidates"]=[other]
        snap["sections"].append({"section":"BSE","status":"READY","result":result})
        qualification.attach(snap,TODAY)
        summary=snap["stock_qualification"]["horizons"]["SWING"]
        selection=summary["selection"]
        self.assertEqual(selection["unique_company_count"],1)
        self.assertEqual(selection["cross_venue_company_count"],1)
        self.assertEqual(selection["watch_refs"],[{"exchange":"BSE","id":2,"isin":item["isin"]}])
        self.assertIn("REPORTED_REVENUE_DECLINE",item["selection_company_context"]["review_findings"])
        self.assertEqual(summary["recommendations"],[])
        self.assertEqual(summary["qualified_count"],0)

    def test_invalid_or_conflicting_identity_excluded(self):
        from copy import deepcopy
        snap,item,group=fixture()
        duplicate=deepcopy(item)
        duplicate["isin"]="INE009A01021"
        unidentified=deepcopy(item)
        unidentified.update(id=3,isin="UNKNOWN")
        group["candidates"].extend([duplicate,unidentified])
        qualification.attach(snap,TODAY)
        selection=snap["stock_qualification"]["horizons"]["SWING"]["selection"]
        self.assertEqual(selection["conflicting_listing_count"],1)
        self.assertEqual(selection["unidentified_listing_count"],1)
        self.assertEqual(selection["watch_refs"],[])

    def test_top_five_distinct_and_stale_venue_excluded(self):
        from copy import deepcopy
        snap,item,group=fixture()
        group["candidates"]=[]
        for i in range(7):
            row=deepcopy(item)
            row.update(id=i+1,symbol="TEST"+str(i),isin="INE000A0101"+str(i),rank_score=i)
            group["candidates"].append(row)
        stale=deepcopy(snap["sections"][0])
        stale.update(section="BSE",status="STALE")
        snap["sections"].append(stale)
        qualification.attach(snap,TODAY)
        selection=snap["stock_qualification"]["horizons"]["SWING"]["selection"]
        self.assertEqual(selection["unique_company_count"],7)
        self.assertEqual(selection["ready_markets"],["NSE"])
        self.assertEqual([r["id"] for r in selection["watch_refs"]],[7,6,5,4,3])


    def test_gap_stress_is_review_only_and_keeps_execution_blockers(self):
        snap,item,_=fixture()
        item["price_structure"]={"as_of":item["as_of"],"scenario_status":"ILLUSTRATIVE_HISTORICAL_GEOMETRY",
            "scenario":{"reward_to_risk":2.5},"risk_sensitivity":{"status":"ILLUSTRATIVE_COST_AND_GAP_STRESS",
                "as_of":item["as_of"],"scenarios":[{"cost_bps_per_side":30,"reference_meets_stressed_ratio":False}]}}
        qualification.attach(snap,TODAY)
        report=item["stock_qualification"]
        self.assertIn("ILLUSTRATIVE_GAP_STRESS_RATIO_BELOW_ASSUMPTION",report["review_findings"])
        self.assertIn("LIVE_SPREAD_AND_EXECUTION_LIQUIDITY_REQUIRED",report["blockers"])
        self.assertEqual(snap["stock_qualification"]["horizons"]["SWING"]["recommendations"],[])
