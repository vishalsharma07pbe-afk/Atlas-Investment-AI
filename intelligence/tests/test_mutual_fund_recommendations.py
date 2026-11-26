import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch
import json
import sqlite3
from app import mutual_fund_recommendations as recommendations
from app.mutual_fund_recommendations import FundEvidence,rank_candidates,suitability,_official_history_candidates,_research_reports

def strong(**changes):
    values=dict(identifier="FUND-A",name="Fund A Direct Growth",category="LARGE_CAP",category_verified=True,
      plan="DIRECT",option="GROWTH",nav=100,nav_date="2026-11-16",nav_age_days=1,history_years=5,
      returns_1y=14,returns_3y=16,returns_5y=15,peer_percentile=88,benchmark_hit_rate=.75,
      worst_rolling_return=3,max_drawdown=-18,volatility=14,expense_ratio=.45,
      riskometer="VERY_HIGH",riskometer_date="2026-10-31")
    values.update(changes);return FundEvidence(**values)

class RecommendationEngineTests(unittest.TestCase):
    def test_strong_returns_do_not_create_growth_outlook_without_forward_evidence(self):
        result=rank_candidates([strong()],"LARGE_CAP",84,"HIGH")
        self.assertEqual(len(result["top_performers"]),1)
        self.assertEqual(result["growth_outlook"],[])
        self.assertIn("RECENT_PORTFOLIO_DISCLOSURE",result["excluded"][0]["growth_outlook_missing"])

    def test_growth_requires_current_portfolio_and_coverage(self):
        fund=strong(portfolio_age_days=20,portfolio_coverage=.95,earnings_coverage=.8,
          valuation_coverage=.75,earnings_growth=15,valuation_attractiveness=70,
          sector_driver_score=65,concentration_risk=25,liquidity_score=80)
        result=rank_candidates([fund],"LARGE_CAP",84,"MODERATE")
        self.assertEqual(result["growth_outlook"][0]["fund"]["identifier"],"FUND-A")

    def test_exact_official_history_populates_only_supported_evidence(self):
        row={"scheme_code":123456,"scheme_name":"Example Direct Growth",
             "category":"Open Ended Schemes(Equity Scheme - Large Cap Fund)",
             "amfi_plan":"DIRECT","amfi_option":"GROWTH","isin_growth":"INF179K01BB2",
             "amfi_metadata_date":"2026-11-23","nav_date":"2026-11-23","nav":100.5,
             "observations":700,"sources":["AMFI","MFAPI"],"cagr_1y_percent":12,
             "cagr_3y_percent":14,"drawdown_3y_percent":-17,"weekly_volatility_percent":13,
             "sample_peer_percentile":80,"worst_rolling_52w_annualized_percent":-8}
        history={"comparison_date":"2026-11-23","items":[row]}
        candidates=_official_history_candidates(history,"LARGE_CAP",date(2026,11,24))
        self.assertEqual(len(candidates),1)
        candidate=candidates[0]
        self.assertEqual(candidate.identifier,"123456")
        self.assertTrue(candidate.category_verified)
        self.assertEqual(candidate.nav_age_days,1)
        self.assertEqual(candidate.returns_3y,14)
        self.assertIsNone(candidate.expense_ratio)
        self.assertIsNone(candidate.benchmark_hit_rate)
        ranked=rank_candidates(candidates,"LARGE_CAP",84,"HIGH")
        self.assertEqual(ranked["top_performers"],[])
        self.assertEqual(ranked["growth_outlook"],[])
        self.assertIn("EXPENSE_RATIO",ranked["excluded"][0]["top_performer_missing"])
        for changed in ({"amfi_plan":"REGULAR"},{"amfi_option":None},{"isin_growth":None},
                        {"category":"Open Ended Schemes(Equity Scheme - Mid Cap Fund)"},
                        {"nav_date":"2026-11-22"},{"amfi_metadata_date":"2026-11-01"},
                        {"sources":["MFAPI"]}):
            self.assertEqual(_official_history_candidates({**history,"items":[{**row,**changed}]},"LARGE_CAP",date(2026,11,24)),[])
        self.assertEqual(_official_history_candidates({**history,"items":[row,row]},"LARGE_CAP",date(2026,11,24)),[])

    def test_36_month_goal_is_flagged_as_poor_fit(self):
        fit=suitability("LARGE_CAP",36,"HIGH")
        self.assertEqual(fit["status"],"POOR_FIT")
        self.assertIn("POOR_FIT_FOR_36_MONTH_GOAL",fit["flags"])

    def test_specialized_categories_are_not_ranked_as_equity(self):
        for category in ("AGGRESSIVE_HYBRID","CORPORATE_BOND","SHORT_DURATION"):
            result=rank_candidates([strong(category=category)],category,84,"HIGH")
            self.assertEqual(result["top_performers"],[])
            self.assertIn("CATEGORY_SPECIFIC_RISK_MODEL_REQUIRED",result["excluded"][0]["top_performer_missing"])
        self.assertNotIn("POOR_FIT_FOR_36_MONTH_GOAL",suitability("CORPORATE_BOND",36,"LOW")["flags"])

    def test_invalid_evidence_duplicates_and_unsuitable_funds_are_not_picks(self):
        for fund in (strong(nav_age_days=-1),strong(peer_percentile=float("nan")),
                     strong(benchmark_hit_rate=1.1),strong(expense_ratio=-1),strong(passive=True)):
            self.assertEqual(rank_candidates([fund],"LARGE_CAP",84,"HIGH")["top_performers"],[])
        self.assertEqual(rank_candidates([strong(),strong()],"LARGE_CAP",84,"HIGH")["top_performers"],[])
        self.assertEqual(rank_candidates([strong()],"LARGE_CAP",36,"HIGH")["top_performers"],[])
        qualified=rank_candidates([strong(identifier=str(i)) for i in range(8)],"LARGE_CAP",84,"HIGH")
        self.assertEqual(qualified["top_eligible_count"],8)
        self.assertEqual(len(qualified["top_performers"]),5)

    def test_full_cohort_not_just_trailing_return_leaders(self):
        row={"scheme_code":123456,"scheme_name":"Example Direct Growth",
             "category":"Open Ended Schemes(Equity Scheme - Multi Cap Fund)",
             "amfi_plan":"DIRECT","amfi_option":"GROWTH","isin_growth":"INF179K01BB2",
             "amfi_metadata_date":"2026-11-23","nav_date":"2026-11-23","nav":100.5,
             "observations":700,"sources":["AMFI","MFAPI"],"cagr_3y_percent":14}
        history={"comparison_date":"2026-11-23","items":[row],
                 "research_candidates":[{**row,"scheme_code":123456+i,"isin_growth":f"INF000A{i:05d}"} for i in range(12)]}
        self.assertEqual(len(_official_history_candidates(history,"MULTI_CAP",date(2026,11,24))),12)

    def test_integrated_report_retains_gates_and_exact_secondary_identity(self):
        fund=strong(identifier="123456",expense_ratio=None,benchmark_hit_rate=None,
                    riskometer=None,riskometer_date=None)
        ranked=rank_candidates([fund],"LARGE_CAP",84,"HIGH")
        report=_research_reports([fund],ranked,
            [{"scheme_code":123456,"sources":["AMFI","MFAPI"]}],
            [{"scheme_code":"123456","ter_percent":0.1}],
            [{"scheme_code":"999999","portfolio_date":"2026-10-31"}])[0]
        self.assertEqual(report["historical"]["returns_3y"],16)
        self.assertEqual(report["historical"]["sources"],["AMFI","MFAPI"])
        self.assertTrue(report["secondary_disclosure_available"])
        self.assertEqual(report["secondary_disclosure"]["ter_percent"],0.1)
        self.assertEqual(report["secondary_disclosure"]["status"],"SECONDARY_REPORTED_NOT_INDEPENDENTLY_VERIFIED")
        self.assertFalse(report["secondary_portfolio_available"])
        self.assertEqual(report["top_performer"]["status"],"WITHHELD")
        self.assertIn("EXPENSE_RATIO",report["top_performer"]["missing"])
        self.assertIn("BENCHMARK_HIT_RATE",report["top_performer"]["missing"])
        self.assertEqual(report["growth_outlook"]["status"],"WITHHELD")
        self.assertIsNone(report["top_performer"]["published_rank"])
        self.assertEqual(ranked["top_performers"],[])
        self.assertEqual(ranked["growth_outlook"],[])

    def test_reports_distinguish_qualified_beyond_published_five_and_missing_metrics(self):
        funds=[strong(identifier=str(i)) for i in range(6)]
        ranked=rank_candidates(funds,"LARGE_CAP",84,"HIGH")
        reports=_research_reports(list(reversed(funds)),ranked,[],[],[])
        self.assertEqual([row["identifier"] for row in reports],list(map(str,range(6))))
        self.assertEqual(reports[0]["top_performer"]["published_rank"],1)
        self.assertEqual(reports[5]["top_performer"]["status"],"QUALIFIED")
        self.assertIsNone(reports[5]["top_performer"]["published_rank"])
        self.assertEqual(reports[5]["growth_outlook"]["status"],"WITHHELD")
        self.assertEqual(reports,_research_reports(funds,ranked,[],[],[]))
        incomplete=strong(identifier="123456",returns_3y=None,peer_percentile=None)
        ranked=rank_candidates([incomplete],"LARGE_CAP",84,"HIGH")
        report=_research_reports([incomplete],ranked,[],[],[])[0]
        self.assertIsNone(report["historical"]["returns_3y"])
        self.assertIsNone(report["historical"]["sample_peer_percentile"])

    def test_history_gate_counts_reconcile_with_sample(self):
        gates={"OFFICIAL_ANCHOR_UNAVAILABLE":1,"COMPARISON_DATE_MISMATCH":2,
               "HISTORY_QUALITY_OR_LENGTH":3,"ELIGIBLE":4}
        history={"sample_count":10,"eligible_count":4,"history_gate_counts":gates}
        self.assertEqual(recommendations._history_gate_counts(history),gates)
        for invalid in ({**history,"sample_count":9},{**history,"eligible_count":3},
                        {**history,"history_gate_counts":{**gates,"EXTRA":0}},
                        {**history,"history_gate_counts":{**gates,"ELIGIBLE":True}}):
            self.assertIsNone(recommendations._history_gate_counts(invalid))

    def test_dashboard_persists_the_same_reports_without_secondary_promotion(self):
        today=datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()
        row={"scheme_code":123456,"scheme_name":"Integrated Fund",
             "category":"Open Ended Schemes(Equity Scheme - Large Cap Fund)",
             "amfi_plan":"DIRECT","amfi_option":"GROWTH","isin_growth":"INF179K01BB2",
             "amfi_metadata_date":today,"nav_date":today,"nav":100.5,
             "observations":700,"sources":["AMFI","MFAPI"],"cagr_3y_percent":14}
        history={"category":"LARGE_CAP","comparison_date":today,"items":[row],
                 "research_candidates":[row],"universe_count":1,"eligible_count":1,
                 "sample_count":1,"history_gate_counts":{"OFFICIAL_ANCHOR_UNAVAILABLE":0,
                    "COMPARISON_DATE_MISMATCH":0,"HISTORY_QUALITY_OR_LENGTH":0,"ELIGIBLE":1}}
        db=sqlite3.connect(":memory:")
        try:
            with patch.object(recommendations,"_catalog_candidates",return_value=([],{"official_category_verified":0,"dated_nav_history_eligible":0})), \
                 patch.object(recommendations,"backend_json",return_value=history), \
                 patch.object(recommendations.fund_disclosures,"matched",return_value=[{"scheme_code":"123456","ter_percent":0.1}]), \
                 patch.object(recommendations.fund_portfolios,"matched",return_value=[]), \
                 patch.object(recommendations.fund_portfolios,"overlap",return_value={"pairs":[]}), \
                 patch.object(recommendations.nav_catalog,"_connect",return_value=db):
                first=recommendations.dashboard("LARGE_CAP",84,"HIGH")
                second=recommendations.dashboard("LARGE_CAP",84,"HIGH")
            self.assertEqual(first["snapshot_hash"],second["snapshot_hash"])
            self.assertEqual(first["historical_coverage"]["eligible_count"],1)
            self.assertEqual(first["historical_coverage"]["universe_count"],1)
            self.assertEqual(first["historical_coverage"]["history_gate_counts"]["ELIGIBLE"],1)
            self.assertEqual(first["top_performers"],[])
            self.assertEqual(first["growth_outlook"],[])
            report=first["research_reports"][0]
            self.assertTrue(report["secondary_disclosure_available"])
            self.assertIn("EXPENSE_RATIO",report["top_performer"]["missing"])
            stored=db.execute("SELECT result_json FROM mf_recommendation_snapshots").fetchall()
            self.assertEqual(len(stored),1)
            self.assertEqual(json.loads(stored[0][0])["research_reports"],first["research_reports"])
        finally:
            db.close()

    def test_reports_include_secondary_context_beyond_display_five(self):
        funds=[strong(identifier=str(123450+i),expense_ratio=None,riskometer=None,riskometer_date=None)
               for i in range(8)]
        ranked=rank_candidates(funds,"LARGE_CAP",84,"HIGH")
        disclosed=[{"scheme_code":fund.identifier,"ter_percent":0.7,"riskometer":"HIGH"} for fund in funds]
        reports=_research_reports(funds,ranked,[],disclosed,[])
        self.assertEqual(len(reports),8)
        self.assertTrue(all(r["secondary_disclosure_available"] for r in reports))
        self.assertTrue(all(r["secondary_disclosure"]["ter_percent"]==0.7 for r in reports))
        self.assertTrue(all("EXPENSE_RATIO" in r["top_performer"]["missing"] for r in reports))
        self.assertTrue(all(r["top_performer"]["status"]=="WITHHELD" for r in reports))
        self.assertEqual(ranked["top_performers"],[])

    def test_ties_are_reproducible_by_stable_identifier(self):
        result=rank_candidates([strong(identifier="B"),strong(identifier="A")],"LARGE_CAP",84,"HIGH")
        self.assertEqual([x["fund"]["identifier"] for x in result["top_performers"]],["A","B"])


    def test_rolling_peer_context_validated_and_not_benchmark_evidence(self):
        from app.mutual_fund_recommendations import _rolling_peer_context
        block={"status":"MATCHED_SAMPLE_ONLY","matched_windows":100,"total_windows":105,
               "minimum_peer_count":4,"above_median_windows":60,"below_median_windows":30,"tied_windows":10,
               "above_median_percent":60.0,"median_difference_pp":1.5,"worst_difference_pp":-10}
        self.assertEqual(_rolling_peer_context({"rolling_peer_consistency":block})["above_median_percent"],60)
        for key,value in (("matched_windows",83),("minimum_peer_count",3),("above_median_percent",90),("median_difference_pp",float("nan")),("tied_windows",0)):
            self.assertIsNone(_rolling_peer_context({"rolling_peer_consistency":{**block,key:value}}))

    def test_unified_assessment_keeps_reported_strengths_conflicts_and_gates_separate(self):
        fund=strong(identifier="123456",expense_ratio=None,benchmark_hit_rate=None,worst_rolling_return=-8)
        ranked=rank_candidates([fund],"LARGE_CAP",84,"HIGH")
        rolling={"status":"MATCHED_SAMPLE_ONLY","matched_windows":100,"total_windows":105,
                 "minimum_peer_count":4,"above_median_windows":30,"below_median_windows":60,"tied_windows":10,
                 "above_median_percent":30.0,"median_difference_pp":-1.5,"worst_difference_pp":-10}
        source=[{"scheme_code":123456,"sources":["AMFI","MFAPI"],"rolling_peer_consistency":rolling}]
        disclosure=[{"scheme_code":"123456","conflicts":["BENCHMARK_CONFLICT"]}]
        portfolio={"scheme_code":"123456","status":"SECONDARY_COMPOSITION_ONLY","exact_listed_equity_weight_percent":80,
                   "underlying_research":{"multi_year_quality":{"status":"REPORTED_MULTI_YEAR_EXPOSURE",
                        "assessed_weight_percent":65,"review_weight_percent":25},"relative_valuation":[{"metric":"PE"}]},
                   "concentration_research":{"category":"LARGE_CAP","status":"EXACT_EQUITY_SUBSET_ONLY",
                       "exact_equity_weight_percent":80,"largest_equity_weight_percent":12,
                       "largest_classified_sector_weight_percent":40,"sector_classified_weight_percent":65,
                       "missing_risk_evidence":["COMPLETE_SECTOR_AND_MARKET_CAP_COVERAGE_REQUIRED"]}}
        result=_research_reports([fund],ranked,source,disclosure,[portfolio])[0]
        assessment=result["research_assessment"]
        self.assertEqual(assessment["status"],"REVIEW_REQUIRED")
        self.assertIn("POSITIVE_REPORTED_THREE_YEAR_CAGR",{r["code"] for r in assessment["supporting_evidence"]})
        codes={r["code"] for r in assessment["review_findings"]}
        self.assertTrue({"BELOW_PEER_MEDIAN_IN_MAJORITY_OF_MATCHED_WINDOWS","REPORTED_MULTI_YEAR_BUSINESS_REVIEW_EXPOSURE",
                         "LARGEST_EXACT_EQUITY_AT_LEAST_TEN_PERCENT","CLASSIFIED_SECTOR_AT_LEAST_THIRTY_PERCENT",
                         "REPORTED_DISCLOSURE_CONFLICTS_REQUIRE_REVIEW","NEGATIVE_WORST_ROLLING_YEAR"}<=codes)
        self.assertIn("PARTIAL_MULTI_YEAR_COMPANY_COVERAGE",assessment["next_evidence_checks"])
        self.assertIn("BENCHMARK_HIT_RATE",assessment["next_evidence_checks"])
        self.assertIn("DATED_UNDERLYING_VALUATION_EVIDENCE_REQUIRED",assessment["next_evidence_checks"])
        self.assertEqual(result["top_performer"]["status"],"WITHHELD")
        self.assertEqual(result["growth_outlook"]["status"],"WITHHELD")
        for portfolios in ([{**portfolio,"scheme_code":"999999"}],[portfolio,portfolio]):
            other=_research_reports([fund],ranked,source,[],portfolios)[0]["research_assessment"]
            self.assertNotIn("REPORTED_MULTI_YEAR_BUSINESS_REVIEW_EXPOSURE",{r["code"] for r in other["review_findings"]})
            self.assertIn("MATCHED_REPORTED_PORTFOLIO_REQUIRED",other["next_evidence_checks"])
        bad={**portfolio,"underlying_research":{"multi_year_quality":{"status":"REPORTED_MULTI_YEAR_EXPOSURE",
                 "assessed_weight_percent":20,"review_weight_percent":90}}}
        other=_research_reports([fund],ranked,source,[],[bad])[0]["research_assessment"]
        self.assertNotIn("REPORTED_MULTI_YEAR_BUSINESS_REVIEW_EXPOSURE",{r["code"] for r in other["review_findings"]})


if __name__=="__main__":unittest.main()
