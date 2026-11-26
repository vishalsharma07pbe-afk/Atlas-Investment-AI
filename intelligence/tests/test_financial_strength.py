import unittest
from datetime import date
from app.financial_strength import summarize

TODAY=date(2026,11,26)
ISIN="INE002A01018"

def row(name,a,b):
    return {"name":name,"history":[{"period":"Mar 2025","value":a},{"period":"Mar 2026","value":b}]}

def block(key,rows=(),detail=()):
    return {"status":"AVAILABLE","source":{"provider":"UPSTOX","endpoint":"/v2/fundamentals/"+ISIN+"/"+key.replace("_","-")},
            "data":{"statement_type":"consolidated","time_period":"yearly","units":"crore","rows":list(rows),"detail_rows":list(detail)}}

def fixture():
    return {"isin":ISIN,"sections":{
        "balance_sheet":block("balance_sheet",detail=[row("Current Assets",100,120),row("Current Liabilities",80,100),row("Net Current Asset",20,19)]),
        "cash_flow":block("cash_flow",[row("operating",50,60),row("investing",-40,-50),row("financing",-5,-8)],
            [row("Total Cash Flow",5,2),row("Cash (Start of the year)",10,15),row("Cash (End of the year)",15,18)])}}

class FinancialStrengthTests(unittest.TestCase):
    def test_same_period_working_capital_and_cash_bridge(self):
        result=summarize(fixture(),TODAY)
        self.assertEqual(result["liquidity"][-1]["current_ratio"],1.2)
        self.assertEqual(result["liquidity"][-1]["working_capital"],20)
        self.assertEqual(result["liquidity"][-1]["net_current_asset_difference"],1)
        self.assertEqual(result["cash_flows"][-1]["combined_cash_flows"],2)
        self.assertEqual(result["cash_flows"][-1]["total_cash_flow_difference"],0)
        self.assertEqual(result["cash_flows"][-1]["balance_movement_difference"],1)
        self.assertIsNone(result["free_cash_flow"])
        self.assertIsNone(result["solvency_rating"])
    def test_legacy_cash_summary_still_works_and_unknowns_not_zero(self):
        value=fixture()
        for key in value["sections"]:
            value["sections"][key]["data"].pop("detail_rows")
        result=summarize(value,TODAY)
        self.assertEqual(result["liquidity"],[])
        self.assertEqual(len(result["cash_flows"]),2)
        self.assertIsNone(result["cash_flows"][-1]["reported_total_cash_flow"])
        self.assertIsNone(result["cash_flows"][-1]["balance_movement_difference"])
    def test_scope_mismatch_duplicate_and_zero_liabilities_fail_closed(self):
        value=fixture()
        value["sections"]["balance_sheet"]["data"]["detail_rows"][1]["history"][-1]["value"]=0
        value["sections"]["cash_flow"]["data"]["rows"].append(row("operating",50,60))
        result=summarize(value,TODAY)
        self.assertEqual(result["liquidity"],[])
        self.assertEqual(result["cash_flows"],[])
        value=fixture()
        value["sections"]["cash_flow"]["data"]["statement_type"]="standalone"
        self.assertEqual(summarize(value,TODAY)["cash_flows"],[])
        value=fixture()
        value["sections"]["cash_flow"]["source"]["endpoint"]="/wrong"
        self.assertEqual(summarize(value,TODAY)["cash_flows"],[])
    def test_mixed_fiscal_periods_and_stale_latest_withheld(self):
        value=fixture()
        value["sections"]["cash_flow"]["data"]["rows"][1]["history"][-1]["period"]="Dec 2025"
        self.assertEqual(summarize(value,TODAY)["cash_flows"],[])
        self.assertEqual(summarize(fixture(),date(2028,1,1))["liquidity"],[])
