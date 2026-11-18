import unittest
from app.mutual_fund_recommendations import FundEvidence,rank_candidates,suitability

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

    def test_36_month_goal_is_flagged_as_poor_fit(self):
        fit=suitability("LARGE_CAP",36,"HIGH")
        self.assertEqual(fit["status"],"POOR_FIT")
        self.assertIn("POOR_FIT_FOR_36_MONTH_GOAL",fit["flags"])

    def test_ties_are_reproducible_by_stable_identifier(self):
        result=rank_candidates([strong(identifier="B"),strong(identifier="A")],"LARGE_CAP",84,"HIGH")
        self.assertEqual([x["fund"]["identifier"] for x in result["top_performers"]],["A","B"])

if __name__=="__main__":unittest.main()
