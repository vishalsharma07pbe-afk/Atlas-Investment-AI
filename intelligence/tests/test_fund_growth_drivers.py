import unittest
from datetime import datetime,timezone,timedelta
from app import fund_growth_drivers as g
NOW=datetime(2026,11,27,5,tzinfo=timezone.utc)
A="INE002A01018"
B="INE009A01021"
def report(isin,profit=150,period="2026-09-30",stamp=NOW):
    series={}
    for key,value in (("revenue",150),("net_profit",profit)):
        series[key]=[{"period":"2025-06-30","value":100},{"period":"2025-09-30","value":100},{"period":"2026-06-30","value":110},{"period":period,"value":value}]
    return {"isin":isin,"retrieved_at":stamp.isoformat(),"sections":{"quarterly_income":{"status":"AVAILABLE",
        "source":{"provider":"UPSTOX","endpoint":f"/v2/fundamentals/{isin}/income-statement"},
        "data":{"statement_type":"consolidated","time_period":"quarterly","units":"crore","series":series}}}}
class GrowthDriversTests(unittest.TestCase):
    def test_weights_and_negative_base_no_forecast(self):
        holdings=[{"isin":A,"weight_percent":70},{"isin":B,"weight_percent":20}]
        result=g.summarize(holdings,{A:report(A),B:report(B,-10)},NOW)
        self.assertEqual(result["assessed_weight_percent"],90)
        self.assertEqual(result["review_weight_percent"],20)
        self.assertEqual(result["quarter_cohorts"][0]["joint_coverage_weight_percent"],70)
        self.assertEqual(result["quarter_cohorts"][0]["joint_growth_weight_percent"],70)
        self.assertIsNone(result["forecast_nav_return_percent"])
        self.assertEqual(g.summarize(holdings,{A:report(A,stamp=NOW-timedelta(hours=25))},NOW)["assessed_weight_percent"],0)
        self.assertEqual(g.summarize([holdings[0],holdings[0]],{},NOW)["status"],"INVALID_HOLDING_IDENTITIES")
    def test_growth_review_requires_same_period_and_exact_scheme(self):
        q=g.summarize([{"isin":A,"weight_percent":75}],{A:report(A)},NOW)
        p={"scheme_code":"123456","status":"SECONDARY_COMPOSITION_ONLY","portfolio_date":"2026-10-31","underlying_research":{"quarterly_growth_drivers":q}}
        r={"identifier":"123456","category":"LARGE_CAP","plan":"DIRECT","option":"GROWTH","nav_date":"2026-11-26","name":"Example"}
        result=g.readiness("LARGE_CAP",[r],[p],NOW.date())
        self.assertEqual(result["items"][0]["state"],"POSITIVE_HISTORICAL_DRIVERS_ONLY")
        self.assertFalse(result["items"][0]["qualified"])
        self.assertFalse(g.readiness("LARGE_CAP",[r,r],[p],NOW.date())["items"])
        self.assertFalse(g.readiness("CORPORATE_BOND",[r],[p],NOW.date())["items"])

    def test_fund_forward_experiment_respects_weight_and_original_quarter(self):
        raw=report(A)
        raw["sections"]["quarterly_income"]["source"]["retrieved_at"]=NOW.isoformat()
        for series in raw["sections"]["quarterly_income"]["data"]["series"].values():
            series.insert(2,{"period":"2025-12-31","value":120})
        q=g.summarize([{"isin":A,"weight_percent":75}],{A:raw},NOW)
        e=q["experimental_forward_cohorts"][0]
        self.assertEqual(e["target_quarter"],"2026-12-31")
        self.assertEqual(e["covered_weight_percent"],75)
        self.assertEqual(e["positive_joint_growth_weight_percent"],75)
        self.assertEqual(e["covered_subset_profit_persistence_percent"],50)
        self.assertFalse(e["qualified"])
        self.assertIsNone(q["forward_earnings_coverage_percent"])
        self.assertIsNone(q["forecast_nav_return_percent"])
        p={"scheme_code":"123456","status":"SECONDARY_COMPOSITION_ONLY","portfolio_date":"2026-10-31","underlying_research":{"quarterly_growth_drivers":q}}
        r={"identifier":"123456","category":"LARGE_CAP","plan":"DIRECT","option":"GROWTH","nav_date":"2026-11-26","name":"Example"}
        self.assertEqual(g.readiness("LARGE_CAP",[r],[p],NOW.date())["items"][0]["experimental_forward"],e)
        e["target_quarter"]="2027-03-31"
        self.assertIsNone(g.readiness("LARGE_CAP",[r],[p],NOW.date())["items"][0]["experimental_forward"])
