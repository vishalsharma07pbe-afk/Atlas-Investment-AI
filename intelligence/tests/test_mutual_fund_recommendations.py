import unittest
from datetime import date
from app.mutual_fund_recommendations import FundEvidence,rank_candidates,suitability,_official_history_candidates

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

    def test_ties_are_reproducible_by_stable_identifier(self):
        result=rank_candidates([strong(identifier="B"),strong(identifier="A")],"LARGE_CAP",84,"HIGH")
        self.assertEqual([x["fund"]["identifier"] for x in result["top_performers"]],["A","B"])

if __name__=="__main__":unittest.main()
