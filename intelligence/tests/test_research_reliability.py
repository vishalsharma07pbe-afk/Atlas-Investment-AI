import unittest
import json
from datetime import date,timedelta
from app.research_reliability import cohort,attach
from app.horizon_research import VERSION

TODAY=date(2026,11,24)

def row(isin="INE002A01018", day=date(2026,8,1), status="OBSERVED", end=110, method=VERSION):
    maturity=day+timedelta(days=14)
    return {"published_at":day.isoformat()+"T10:00:00+00:00",
        "observed_date":(day-timedelta(days=1)).isoformat(),"maturity_date":maturity.isoformat(),
        "status":status,"evidence":json.dumps({"isin":isin,"methodology":method,"adjustment_status":"ADJUSTED"}),
        "outcome":json.dumps({"entry_date":(day+timedelta(days=1)).isoformat(),"exit_date":maturity.isoformat(),
            "entry_close":100,"exit_close":end,"source_code":"TEST"})}

class ResearchReliabilityTests(unittest.TestCase):
    def test_missing_early_outcome_does_not_select_later_overlapping_winner(self):
        rows=[row(status="EVIDENCE_GAP"),row(day=date(2026,8,5)),row(day=date(2026,9,1))]
        result=cohort(rows,"SWING",TODAY)
        self.assertEqual(result["selected_mature_watches"],2)
        self.assertEqual(result["observed_outcomes"],1)
        self.assertEqual(result["overlap_excluded"],1)
        self.assertEqual(result["coverage_percent"],50)
        self.assertIn("INCOMPLETE_OUTCOME_COVERAGE",result["blockers"])
        self.assertEqual(result["status"],"INSUFFICIENT_EVIDENCE")

    def test_old_methodology_and_unmatured_observations_excluded(self):
        result=cohort([row(method="OLD"),row(day=TODAY-timedelta(days=3))],"SWING",TODAY)
        self.assertEqual(result["incompatible_excluded"],1)
        self.assertEqual(result["immature_excluded"],1)
        self.assertFalse(result["cost_scenarios"])

    def test_cost_sensitive_descriptive_sample_never_calibrated(self):
        rows=[row(isin="IN"+str(i).zfill(10),day=day,end=100.5)
              for day in (date(2026,5,1),date(2026,6,1),date(2026,7,1))
              for i in range(10)]
        result=cohort(rows,"SWING",TODAY)
        self.assertEqual(result["observed_outcomes"],30)
        self.assertEqual(result["status"],"COST_SENSITIVE_OR_NEGATIVE_SAMPLE")
        self.assertGreater(result["cost_scenarios"][0]["mean_net_change_percent"],0)
        self.assertLess(result["cost_scenarios"][-1]["mean_net_change_percent"],0)
        self.assertEqual(cohort(rows,"SWING",TODAY,True)["status"],"INSUFFICIENT_EVIDENCE")

    def test_conflicting_evidence_does_not_remove_existing_blockers(self):
        item={"as_of":"2026-11-23","adjustment_status":"RAW_UNADJUSTED",
              "company_evidence":{"available_sections":1,"financial_trends":{"items":[
                {"metric":"NET_PROFIT","direction":"DECREASED","latest_period_may_be_stale":False}]}},
              "news_evidence":{"status":"REVIEW_AVAILABLE","articles":[{"topics":["REGULATORY"]}]}}
        snapshot={"enabled":True,"sections":[{"section":"NSE","status":"READY","result":{"horizons":{
            "SWING":{"blockers":["STRATEGY_BACKTEST_NOT_VERIFIED"],"candidates":[item]}}}}]}
        attach(snapshot,{"horizons":{}},TODAY)
        result=item["research_reliability"]
        self.assertEqual(result["status"],"REVIEW_CONFLICTING_EVIDENCE")
        self.assertIn("NET_PROFIT_DETERIORATION_REVIEW",result["warnings"])
        self.assertIn("REGULATORY_HEADLINE_REVIEW",result["warnings"])
        self.assertIn("STRATEGY_BACKTEST_NOT_VERIFIED",result["blockers"])
        self.assertIn("ADJUSTED_PRICE_HISTORY_REQUIRED",result["blockers"])

    def test_conclusion_preserves_blockers_and_surfaces_negative_replay(self):
        from app.research_reliability import attach_conclusions
        item={"as_of":"2026-11-23","research_reliability":{"warnings":[],"blockers":["VALUATION_NOT_VERIFIED"]},
              "matched_strategy_replay":{"as_of":"2026-11-23","status":"REPLAY_OBSERVED","small_sample":True,
                   "cost_scenarios":[{"net_return_percent":-1}]},
              "ai_review":{"reviews":[{"provider":"OLLAMA"}]}}
        snapshot={"enabled":True,"sections":[{"section":"NSE","status":"READY","result":{"horizons":{
            "SWING":{"status":"TECHNICAL_WATCH_ONLY","blockers":["EVENT_RISK_NOT_VERIFIED"],"candidates":[item]}}}}]}
        attach_conclusions(snapshot)
        result=item["research_conclusion"]
        self.assertEqual(result["status"],"REVIEW_REQUIRED")
        self.assertIn("MATCHED_REPLAY_NONPOSITIVE_AFTER_COSTS",result["warnings"])
        self.assertIn("EVENT_RISK_NOT_VERIFIED",result["blockers"])
        self.assertIn("VALUATION_NOT_VERIFIED",result["blockers"])
        self.assertEqual(result["evidence"]["valuation"],"NOT_VERIFIED")
        self.assertEqual(result["evidence"]["ai"],"COMMENTARY_AVAILABLE")

    def test_conclusion_connects_business_deterioration_without_lifting_valuation_gate(self):
        from app.research_reliability import attach_conclusions
        item={"company_evidence":{"fundamental_quality":{"status":"REVIEW_REQUIRED",
            "warnings":["NET_MARGIN_DETERIORATION_REVIEW"],"valuation":{"status":"SECTOR_COMPARISON_ONLY"}}}}
        snapshot={"enabled":True,"sections":[{"section":"NSE","status":"READY","result":{"horizons":{
            "LONG_TERM":{"blockers":["VALUATION_NOT_VERIFIED"],"candidates":[item]}}}}]}
        attach_conclusions(snapshot)
        result=item["research_conclusion"]
        self.assertEqual(result["status"],"REVIEW_REQUIRED")
        self.assertIn("NET_MARGIN_DETERIORATION_REVIEW",result["warnings"])
        self.assertEqual(result["evidence"]["valuation"],"SECTOR_COMPARISON_ONLY")
        self.assertIn("VALUATION_NOT_VERIFIED",result["blockers"])
