import unittest
from datetime import date
from app.earnings_quality import summarize

ISIN="INE002A01018"
# March 2025 is exactly 18 calendar months old here; March 2026
# summary is newer but the detailed bridge remains within the freshness gate.
TODAY=date(2026,9,26)

def row(name,a,b):
    return {"name":name,"history":[{"period":"Mar 2024","value":a},{"period":"Mar 2025","value":b}]}

def fixture():
    income=[row("Revenue",80,100),row("Other Income",10,15),row("Total Revenue",90,115),
            row("Total Expenses",70,85),row("Profit Before Tax",20,30),row("Tax",5,8),row("Profit After Tax",15,22)]
    def block(key,rows,detail):
        return {"status":"AVAILABLE","source":{"provider":"UPSTOX","endpoint":"/v2/fundamentals/"+ISIN+"/"+key.replace("_","-")},
                "data":{"statement_type":"consolidated","time_period":"yearly","units":"crore","rows":rows,"detail_rows":detail}}
    return {"isin":ISIN,"sections":{
        "income_statement":block("income_statement",[{"name":"revenue","history":[{"period":"Mar 2025","value":115},{"period":"Mar 2026","value":130}]}],income),
        "cash_flow":block("cash_flow",[row("operating",18,20)],[])}}

class EarningsQualityTests(unittest.TestCase):
    def test_all_bridges_and_lag_not_latest_summary(self):
        report=summarize(fixture(),TODAY)
        self.assertEqual(report["status"],"REPORTED_EARNINGS_BRIDGES")
        self.assertEqual(report["period_scope_status"],"DETAIL_OLDER_THAN_SUMMARY")
        self.assertEqual(report["latest_detail_period"],"2025-03")
        self.assertEqual(report["revenue_bridge"][-1]["other_income_percent"],13.0435)
        self.assertEqual(report["pretax_bridge"][-1]["pretax_margin_percent"],26.087)
        self.assertEqual(report["tax_bridge"][-1]["reported_tax_to_pretax_percent"],26.6667)
        self.assertEqual(report["tax_bridge"][-1]["reconciliation_difference"],0)
        self.assertEqual(report["cash_quality"][-1]["cash_minus_profit"],-2)
        self.assertFalse(report["valuation_eligible"])
        self.assertIsNone(report["fair_value"])
    def test_duplicate_missing_and_unmatched_latest_are_not_imputed(self):
        value=fixture()
        value["sections"]["income_statement"]["data"]["detail_rows"].append(row("Tax",4,7))
        value["sections"]["cash_flow"]["data"]["rows"][0]["history"][-1]["period"]="Mar 2026"
        result=summarize(value,TODAY)
        self.assertEqual(result["tax_bridge"],[])
        self.assertEqual(result["cash_quality"],[])
        self.assertTrue(result["revenue_bridge"])
        value["sections"]["income_statement"]["source"]["endpoint"]="/wrong"
        self.assertEqual(summarize(value,TODAY)["status"],"INSUFFICIENT_MATCHED_EVIDENCE")
    def test_loss_year_and_negative_tax_remain_reported(self):
        value=fixture()
        rows=value["sections"]["income_statement"]["data"]["detail_rows"]
        rows[4]["history"][-1]["value"]=-5
        rows[5]["history"][-1]["value"]=-2
        rows[6]["history"][-1]["value"]=-3
        result=summarize(value,TODAY)
        self.assertIsNone(result["tax_bridge"][-1]["reported_tax_to_pretax_percent"])
        self.assertIsNone(result["cash_quality"][-1]["cash_to_profit_ratio"])
        self.assertEqual(result["tax_bridge"][-1]["reconciliation_difference"],0)

    def test_stale_detail_is_withheld_even_with_newer_summary(self):
        value=fixture()
        result=summarize(value,date(2026,11,26))
        self.assertEqual(result["status"],"INSUFFICIENT_MATCHED_EVIDENCE")
        self.assertEqual(result["period_scope_status"],"DETAIL_OLDER_THAN_SUMMARY")
        self.assertEqual(result["latest_detail_period"],"2025-03")
        for key in ("revenue_bridge","pretax_bridge","tax_bridge","cash_quality"):
            self.assertEqual(result[key],[])
        self.assertFalse(result["valuation_eligible"])
        self.assertIsNone(result["fair_value"])
