import unittest
from app.fundamental_quality import summarize


def trend(metric,previous,latest,unit="INR crore",start=2024,end=2025):
    return {"metric":metric,"previous_value":previous,"latest_value":latest,"unit":unit,
            "previous_year":start,"latest_year":end,"latest_period_may_be_stale":False}


def ratio(name,a,b,unit="RATIO",sector_unit="RATIO"):
    return {"name":name,"company_value":a,"sector_value":b,"unit":unit,"sector_unit":sector_unit}


def report(trends=(),ratios=()):
    return {"financial_trends":{"items":list(trends)},"sections":{"ratios":{"status":"AVAILABLE","data":list(ratios)}}}


class FundamentalQualityTests(unittest.TestCase):
    def test_matched_annual_margins_cash_conversion_and_liability_ratio(self):
        result=summarize(report([
            trend("REVENUE",100,200),trend("NET_PROFIT",20,30),
            trend("OPERATING_CASH_FLOW",30,15),trend("TOTAL_ASSETS",100,200),
            trend("TOTAL_LIABILITIES",50,120)]),2026)
        rows={r["metric"]:r for r in result["derived_metrics"]}
        self.assertEqual(rows["NET_MARGIN"]["latest_value"],15)
        self.assertEqual(rows["NET_MARGIN"]["change"],-5)
        self.assertEqual(rows["OPERATING_CASH_TO_PROFIT"]["latest_value"],0.5)
        self.assertEqual(rows["REPORTED_LIABILITIES_TO_ASSETS"]["latest_value"],60)
        self.assertEqual(result["status"],"REVIEW_REQUIRED")
        self.assertIn("NET_MARGIN_DETERIORATION_REVIEW",result["warnings"])
        self.assertIn("OPERATING_CASH_FLOW_DETERIORATION_REVIEW",result["warnings"])

    def test_mismatched_period_unit_and_negative_denominator_not_combined(self):
        result=summarize(report([
            trend("REVENUE",100,200,start=2025,end=2026),
            trend("NET_PROFIT",-5,30),trend("OPERATING_CASH_FLOW",30,15,unit="INR lakh"),
            trend("TOTAL_ASSETS",100,200),trend("TOTAL_LIABILITIES",-5,120)]),2026)
        self.assertEqual(result["derived_metrics"],[])

    def test_sector_comparisons_are_not_fair_values(self):
        result=summarize(report(ratios=[
            ratio("P/E",20,10),ratio("P/B",2,4),
            ratio("ROE",15,10,"PERCENT","PERCENT"),
            ratio("ROCE",20,0,"PERCENT","RATIO")]),2026)
        rows={r["metric"]:r for r in result["sector_comparisons"]}
        self.assertEqual(rows["PE"]["premium_discount_percent"],100)
        self.assertEqual(rows["PB"]["premium_discount_percent"],-50)
        self.assertEqual(rows["ROE"]["difference"],5)
        self.assertNotIn("ROCE",rows)
        self.assertEqual(result["valuation"]["status"],"SECTOR_COMPARISON_ONLY")
        self.assertIsNone(result["valuation"]["fair_value"])
        self.assertIn("RATIO_OBSERVATION_PERIOD_UNVERIFIED",result["gaps"])

    def test_duplicate_negative_and_legacy_ratios_are_not_used(self):
        legacy=ratio("ROE",10,8,"PERCENT","PERCENT")
        del legacy["sector_unit"]
        result=summarize(report(ratios=[ratio("P/E",10,20),ratio("PE",11,20),
                                       ratio("P/B",-2,5),legacy]),2026)
        self.assertEqual(result["sector_comparisons"],[])
        self.assertEqual(result["status"],"UNAVAILABLE")

    def test_stale_and_duplicate_trends_do_not_create_quality_verdict(self):
        result=summarize(report([trend("REVENUE",100,200,start=2020,end=2021),
            trend("NET_PROFIT",10,20),trend("NET_PROFIT",10,30)]),2026)
        self.assertEqual(result["status"],"UNAVAILABLE")
        self.assertEqual(result["strengths"],[])
        self.assertEqual(result["warnings"],[])
