import unittest
import json
from datetime import date,timedelta
from app.research_reliability import cohort,attach
from app.horizon_research import VERSION
from app.watch_outcomes import OUTCOME_EVIDENCE_VERSION

TODAY=date(2026,11,24)

def row(isin="INE002A01018", day=date(2026,8,1), status="OBSERVED", end=110, method=VERSION):
    maturity=day+timedelta(days=14)
    return {"published_at":day.isoformat()+"T10:00:00+00:00",
        "observed_date":(day-timedelta(days=1)).isoformat(),"maturity_date":maturity.isoformat(),
        "status":status,"evidence":json.dumps({"isin":isin,"methodology":method,"adjustment_status":"ADJUSTED"}),
        "outcome":json.dumps({"entry_date":(day+timedelta(days=1)).isoformat(),"exit_date":maturity.isoformat(),
            "entry_close":100,"exit_close":end,"source_code":"TEST","evidence_version":OUTCOME_EVIDENCE_VERSION,
            "calendar_status":"STORED_SESSIONS_MATCHED","corporate_action_status":"NO_RECORDED_CROSSING_ACTION",
            "action_context_through":maturity.isoformat(),"observations":10,"history_fingerprint":"a"*64})}

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
        rows=[row(isin="INE"+str(i).zfill(9),day=day,end=100.5)
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

    def test_legacy_observed_outcome_is_not_a_verified_metric_or_removed_from_denominator(self):
        first=row()
        outcome=json.loads(first["outcome"])
        outcome.pop("evidence_version")
        first["outcome"]=json.dumps(outcome)
        result=cohort([first,row(day=date(2026,9,1))],"SWING",TODAY)
        self.assertEqual(result["selected_mature_watches"],2)
        self.assertEqual(result["observed_outcomes"],1)
        self.assertEqual(result["legacy_or_unverified_observed"],1)
        self.assertEqual(result["coverage_percent"],50)

    def test_conclusion_integrates_growth_discount_ownership_and_benchmark_conflicts(self):
        from app.research_reliability import attach_conclusions
        item={"isin":"INE002A01018","as_of":"2026-11-23",
            "company_evidence":{"isin":"INE002A01018","fundamental_quality":{"warnings":["NET_MARGIN_DETERIORATION_REVIEW"],
                "multi_year_quality":{"status":"REPORTED_MULTI_YEAR_EVIDENCE","metrics":[{"metric":"REVENUE","increasing_years":3,"nonpositive_years":0}]}},
                "peer_research":{"valuation_research":{"status":"UNDATED_PEER_MULTIPLES","metrics":[{"metric":"PE"}],
                    "review_prompt":"DISCOUNT_WITH_REPORTED_DETERIORATION_REVIEW"}},
                "ownership_research":{"status":"COMPARABLE_QUARTERS","review_prompts":[{"category":"fii","change_pp":-2}],
                    "blockers":["STOCK_LEVEL_TRANSACTION_DATA_UNVERIFIED"]}},
            "matched_strategy_replay":{"status":"REPLAY_OBSERVED","as_of":"2026-11-23","cost_scenarios":[
                {"cost_bps_per_side":30,"net_return_percent":2,"net_difference_vs_same_stock_pp":-1,"net_difference_vs_nifty50_pp":-2}]},
            "price_structure":{"as_of":"2026-11-23","scenario_status":"ILLUSTRATIVE_HISTORICAL_GEOMETRY"}}
        snapshot={"enabled":True,"sections":[{"section":"NSE","status":"READY","result":{"horizons":{
            "SWING":{"blockers":["EVENT_RISK_NOT_VERIFIED"],"candidates":[item]}}}}]}
        attach_conclusions(snapshot)
        result=item["research_conclusion"]
        self.assertEqual(result["qualification_status"],"WATCH_ONLY_UNQUALIFIED")
        self.assertEqual(result["status"],"REVIEW_REQUIRED")
        self.assertIn("REVENUE_THREE_ANNUAL_INCREASES",result["supporting_evidence"])
        self.assertIn("PEER_DISCOUNT_WITH_FINANCIAL_DETERIORATION_REVIEW",result["warnings"])
        self.assertIn("REPORTED_FII_OWNERSHIP_DECLINE_REVIEW",result["warnings"])
        self.assertIn("MATCHED_REPLAY_LAGS_SAME_STOCK_AFTER_COSTS",result["warnings"])
        self.assertIn("MATCHED_REPLAY_LAGS_PRICE_INDEX_AFTER_COSTS",result["warnings"])
        self.assertIn("EVENT_RISK_NOT_VERIFIED",result["next_evidence_checks"])
        self.assertIn("STOCK_LEVEL_TRANSACTION_DATA_UNVERIFIED",result["next_evidence_checks"])
        self.assertEqual(result["evidence"]["institutional"],"STOCK_LEVEL_NOT_VERIFIED")
        self.assertEqual(result["evidence"]["reported_ownership"],"COMPARABLE_QUARTERS")
        item["company_evidence"]["isin"]="INE009A01021"
        attach_conclusions(snapshot)
        self.assertEqual(item["research_conclusion"]["supporting_evidence"],[])
        self.assertNotIn("REPORTED_FII_OWNERSHIP_DECLINE_REVIEW",item["research_conclusion"]["warnings"])
        self.assertIn("EXACT_COMPANY_IDENTITY_EVIDENCE_REQUIRED",item["research_conclusion"]["next_evidence_checks"])

    def test_path_metrics_are_separate_from_legacy_return_metrics(self):
        from app.watch_outcomes import RISK_PATH_VERSION
        a=row()
        value=json.loads(a["outcome"])
        value["risk_path"]={"version":RISK_PATH_VERSION,"observations":10,
                            "worst_close_from_entry_percent":-10,"best_close_from_entry_percent":20,
                            "peak_to_trough_close_drawdown_percent":-25}
        a["outcome"]=json.dumps(value)
        b=row(day=date(2026,9,1))
        result=cohort([a,b],"SWING",TODAY)
        self.assertEqual(result["observed_outcomes"],2)
        self.assertEqual(result["risk_path_summary"]["observed_paths"],1)
        self.assertEqual(result["risk_path_summary"]["outcomes_without_path"],1)
        self.assertEqual(result["risk_path_summary"]["coverage_percent"],50)
        self.assertEqual(result["risk_path_summary"]["worst_close_drawdown_percent"],-25)
        value["risk_path"]["peak_to_trough_close_drawdown_percent"]=-5
        a["outcome"]=json.dumps(value)
        result=cohort([a,b],"SWING",TODAY)
        self.assertEqual(result["observed_outcomes"],2)
        self.assertEqual(result["risk_path_summary"]["observed_paths"],0)
