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
