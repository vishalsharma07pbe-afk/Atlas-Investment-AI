import unittest
from app.financial_trends import summarize

def report(history, name="Revenue", units="crore"):
    return {"sections":{"income_statement":{"status":"AVAILABLE","data":{"units":units,"rows":[{"name":name,"history":history}]},"source":{"provider":"UPSTOX"}}}}

def points(*pairs):
    return [{"period":year,"value":value} for year,value in pairs]

class FinancialTrendsTests(unittest.TestCase):
    def test_unsorted_years_and_positive_growth(self):
        result=summarize(report(points(("FY2025",120),("FY2024",100))),2026)
        self.assertEqual(result["status"],"PARTIAL")
        row=result["items"][0]
        self.assertEqual(row["change_percent"],20)
        self.assertEqual(row["direction"],"INCREASED")
        self.assertFalse(row["latest_period_may_be_stale"])
        self.assertIn("NET_PROFIT",result["missing_metrics"])

    def test_ambiguous_periods_missing_years_and_duplicates(self):
        for series in [points(("Q4 2025",120),("FY2024",100)),
                       points(("FY2025",120),("FY2023",100)),
                       points(("FY2025",120),("2025",100)),
                       points(("FY2027",120),("FY2026",100)),
                       points(("FY2025",float("nan")),("FY2024",100))]:
            self.assertEqual(summarize(report(series),2026)["status"],"UNAVAILABLE")
        self.assertEqual(summarize(report(points(("FY2025",120),("FY2024",100)),units=None),2026)["status"],"UNAVAILABLE")

    def test_negative_base_and_stale_period(self):
        result=summarize(report(points(("FY2022",-20),("FY2023",10)),name="Net profit"),2026)
        row=result["items"][0]
        self.assertIsNone(row["change_percent"])
        self.assertEqual(row["change"],30)
        self.assertTrue(row["latest_period_may_be_stale"])

    def test_balance_sheet_and_cash_flow(self):
        result=summarize({"sections":{
            "balance_sheet":{"status":"AVAILABLE","data":{"units":"crore","rows":[
                {"period":"FY2024","total_asset":100,"total_liability":40},
                {"period":"FY2025","total_asset":120,"total_liability":50}]}},
            "cash_flow":{"status":"AVAILABLE","data":{"units":"crore","rows":[
                {"name":"Operating cash flow","history":points(("FY2024",20),("FY2025",-5))}]}}
        }},2026)
        items={row["metric"]:row for row in result["items"]}
        self.assertEqual(items["TOTAL_ASSETS"]["change_percent"],20)
        self.assertEqual(items["TOTAL_LIABILITIES"]["change_percent"],25)
        self.assertIsNone(items["OPERATING_CASH_FLOW"]["change_percent"])
        self.assertEqual(items["OPERATING_CASH_FLOW"]["direction"],"DECREASED")
