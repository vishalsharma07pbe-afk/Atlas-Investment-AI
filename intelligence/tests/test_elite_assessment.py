import unittest
from copy import deepcopy
from app import elite_assessment as ea
from app.steady_momentum import ranked_shortlists

def fixture():
    return {"isin":"INE002A01018","exchange":"NSE","cap_category":"LARGE_CAP","as_of":"2026-11-26",
      "adjustment_status":"ADJUSTED","positive_day_percent":65,"largest_gain_share_percent":10,
      "median_daily_turnover_cr":20,"earnings_growth_percent":25,"eps_growth_percent":25,"sales_growth_percent":15,
      "earnings_basis":"UPSTOX_REPORTED_CONSOLIDATED_ANNUAL","financial_period":"2026-03",
      "reported_pe":20,"reported_sector_pe":25,"ratio_period":"UNVERIFIED",
      "momentum_windows":{"60":{"last_date":"2026-11-26","adjustment_status":"ADJUSTED","positive_day_percent":65,
        "largest_gain_share_percent":10,"return_percent":15,"maximum_close_drawdown_percent":8,"annualized_daily_volatility_percent":20}}}

class EliteAssessmentTests(unittest.TestCase):
    def test_fixed_weights_and_complete_score_not_qualification(self):
        r=ea.assess(fixture())
        self.assertEqual(sum(c["weight"] for c in r["components"]),100)
        self.assertEqual(r["score"],round(sum(c["points"] for c in r["components"]),2))
        self.assertGreater(r["score"],0)
        self.assertLessEqual(r["score"],100)
        self.assertEqual(r["historical_risk"]["historical_price_risk"],"LOW")
        self.assertFalse(r["qualified"])
        self.assertIsNone(r["evidence_coverage"]["probability"])
        self.assertIn("FINAL_QUALIFICATION_VALIDATION_REQUIRED",r["blockers"])
    def test_missing_stale_nonfinite_inputs_never_become_score(self):
        for bad in (None,float("nan"),True):
            row=fixture();row["reported_pe"]=bad
            result=ea.assess(row)
            self.assertIsNone(result["score"])
            self.assertIn("UNDATED_RELATIVE_PE",result["missing_factors"])
        row=fixture();row["momentum_windows"]["60"]["last_date"]="2026-11-25"
        self.assertIsNone(ea.assess(row)["score"])
    def test_high_risk_uses_worse_dimension_and_reduces_score(self):
        row=fixture();baseline=ea.assess(row)["score"]
        row["momentum_windows"]["60"]["annualized_daily_volatility_percent"]=45
        result=ea.assess(row)
        self.assertEqual(result["historical_risk"]["historical_price_risk"],"HIGH")
        self.assertLess(result["score"],baseline)
    def test_optional_evidence_cannot_inflate_score(self):
        row=fixture();baseline=ea.assess(row)
        row["exchange"]="BSE"
        row["quarterly_financials"]={"items":[{"metric":"revenue"}]}
        row["governance_review"]={"findings":["REVIEW"],"blockers":["PLEDGE_REQUIRED"]}
        result=ea.assess(row)
        self.assertEqual(result["score"],baseline["score"])
        self.assertIn("PLEDGE_REQUIRED",result["blockers"])
        self.assertEqual(result["review_findings"],["REVIEW"])
    def test_ranking_scores_only_comparable_complete_rubrics(self):
        strong=fixture();weak=deepcopy(strong);unknown=deepcopy(strong)
        weak["isin"]="INE009A01021";weak["reported_pe"]=30
        unknown["isin"]="INE000A01001";unknown["reported_pe"]=None
        unknown["positive_day_percent"]=100
        for row in (strong,weak,unknown):row["elite_assessment"]=ea.assess(row)
        overall,cap,count=ranked_shortlists([unknown,weak,strong])
        self.assertEqual(overall,[strong,weak,unknown])
        self.assertEqual(count,3)
