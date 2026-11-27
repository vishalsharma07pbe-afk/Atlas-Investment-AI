from datetime import date
import unittest
from app import quarterly_financials as q

class QuarterlyFinancialsTests(unittest.TestCase):
    def raw(self):
        periods=["Jun 2025","Sep 2025","Jun 2026","Sep 2026"]
        return {"type":"consolidated","time_period":"quarterly","units_in":"crore",
          "income_statement":[{"category":k,"history":[{"period":p,"value":v} for p,v in zip(periods,values)]}
          for k,values in (("revenue",[100,100,110,120]),("operating_profit",[20,20,22,30]),("net_profit",[10,10,11,15]))],
          "full_statement":[{"particular":"EPS - Basic","history":[{"period":"Mar 2026","value":99}]}]}
    def result(self,raw):
        today=date(2026,11,27)
        data=q.normalize(raw,today)
        return q.summarize({"isin":"INE002A01018","sections":{"quarterly_income":{"status":"AVAILABLE","data":data,
            "source":{"provider":"UPSTOX","endpoint":"/v2/fundamentals/INE002A01018/income-statement"}}}},today)
    def test_matched_growth_and_margins_without_annual_eps(self):
        result=self.result(self.raw())
        self.assertEqual(result["latest_period"],"2026-09-30")
        self.assertEqual(result["items"][2]["year_over_year_growth_percent"],50)
        self.assertEqual(result["items"][2]["growth_acceleration_pp"],40)
        self.assertEqual(result["operating_margin_percent"],25)
        self.assertEqual(result["net_margin_percent"],12.5)
        self.assertIsNone(result["quarterly_eps"])
        self.assertFalse(result["valuation_eligible"])
    def test_partial_newer_period_never_falls_back(self):
        raw=self.raw();raw["income_statement"][2]["history"].pop()
        result=self.result(raw)
        self.assertEqual(result["status"],"PARTIAL_LATEST_QUARTER")
        self.assertIsNone(result["net_margin_percent"])
        self.assertEqual(len(result["items"]),2)
    def test_duplicates_future_and_annual_scope_rejected(self):
        for bad in ("duplicate","future","annual"):
            raw=self.raw()
            if bad=="duplicate":raw["income_statement"][0]["history"].append(raw["income_statement"][0]["history"][0])
            elif bad=="future":raw["income_statement"][0]["history"][-1]["period"]="Dec 2026"
            else:raw["time_period"]="yearly"
            self.assertEqual(self.result(raw)["status"],"UNAVAILABLE")
    def test_loss_base_is_not_percentage_growth(self):
        raw=self.raw();raw["income_statement"][2]["history"][1]["value"]=-10
        self.assertIsNone(self.result(raw)["items"][2]["year_over_year_growth_percent"])
