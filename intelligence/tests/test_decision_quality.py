import unittest
from datetime import date
from app import decision_quality as q

TODAY=date(2026,11,28)
def stock():
    return {"isin":"INE002A01018","tier":"ADJUSTED_JOINT","qualified":False,"as_of":"2026-11-27","close":100,
        "action":"RESEARCH_FOR_ENTRY","risk":"MEDIUM","score":90,
        "observed_facts":{"earnings_growth_percent":20,"eps_growth_percent":20,"reported_pe":20,"reported_sector_pe":25,"median_daily_turnover_cr":50},
        "price_plan":{"reference":100,"stop_scenario":95,"target_scenario":110},
        "growth_outlook":{"status":"UNCALIBRATED_EARNINGS_SCENARIO","revenue_yoy_percent":20,"profit_yoy_percent":25},
        "valuation_scenario":{"status":"OPERATOR_SOURCE_BOUND_VALUATION_SCENARIO","qualified":False,"isin":"INE002A01018","price_date":"2026-11-27","scenarios":[{"case":"BASE","upside_downside_percent":15}]}}

def fund():
    return {"identifier":"123456","tier":"DRIVER_SUPPORTED","qualified":False,"nav_date":"2026-11-27","score":95,"action":"COMPARE_FOR_SIP",
        "observed_facts":{"historical_cagr_percent":15},
        "growth_outlook":{"status":"UNCALIBRATED_UNDERLYING_GROWTH_SCENARIO","coverage_percent":80,"revenue_yoy_percent":12,"profit_yoy_percent":15},
        "fund_evidence":{"weekly_drawdown_percent":-20,"annualized_volatility_percent":15,"ter_status":"REPORTED_NOT_INDEPENDENTLY_AUTHENTICATED",
            "ter_percent":.7,"ter_date":"2026-11-27","ter_basis":"AMFI_WEBSITE_OPERATOR_CROSSWALK",
            "benchmark_context":{"basis":"MATCHED_LOCAL_TRI_EXPORT","three_year_difference_pp":2,"rolling_outperformance_percent":70}}}

class FinalDecisionQualityTest(unittest.TestCase):
    def test_unknown_is_not_adverse_or_a_positive_override(self):
        row=stock();self.assertEqual(q.stock(row,TODAY)["state"],"PRIORITY_RESEARCH")
        row.pop("valuation_scenario")
        result=q.stock(row,TODAY)
        self.assertEqual(result["state"],"EVIDENCE_INCOMPLETE")
        self.assertIn("SOURCE_BOUND_VALUE_SCENARIO",result["missing_checks"])
        self.assertEqual(result["adverse_findings"],[])

    def test_adverse_evidence_cannot_be_outvoted(self):
        row=stock();row["valuation_scenario"]["scenarios"][0]["upside_downside_percent"]=-10
        row["ai_review"]={"state":"PRIORITIZE_REVIEW"}
        self.assertEqual(q.stock(row,TODAY)["state"],"REVIEW_REQUIRED")
        row=fund();self.assertEqual(q.fund(row,TODAY)["state"],"PRIORITY_RESEARCH")
        row["fund_evidence"]["ter_status"]="CONFLICTING_SAME_DATE_TER"
        self.assertEqual(q.fund(row,TODAY)["state"],"REVIEW_REQUIRED")

    def test_final_action_and_observed_performance_hold(self):
        a=stock();b=stock();b["isin"]="INE467B01029";b["risk"]="HIGH"
        report={"status":"RESEARCH_AVAILABLE","stocks":[b,a],"funds":[],"next_steps":["Review"],
            "decision_outcomes":{"states":{"PRIORITY_RESEARCH":{"status":"ADVERSE_OBSERVED_SAMPLE"}}}}
        q.attach(report,TODAY)
        self.assertEqual(report["stocks"][0]["isin"],a["isin"])
        self.assertEqual(a["action"],"WATCH_FOR_CONFIRMATION")
        self.assertEqual(b["action"],"WATCH_FOR_CONFIRMATION")
        self.assertEqual(report["decision_quality"]["stock_allocation_hold"],"ADVERSE_OBSERVED_PRIORITY_SAMPLE")
        self.assertFalse(a["decision_quality"]["qualified"])

    def test_allocation_requires_current_corroboration_without_relabeling_research(self):
        a=stock();a["growth_outlook"]["observed_quarter"]="2026-09-30"
        report={"status":"RESEARCH_AVAILABLE","stocks":[a],"funds":[]}
        q.attach(report,TODAY)
        self.assertEqual(a["decision_quality"]["state"],"PRIORITY_RESEARCH")
        self.assertEqual(a["allocation_evidence_hold"],"CURRENT_FORECAST_ANCHOR_FILING_REQUIRED")
        self.assertEqual(a["action"],"WATCH_FOR_CONFIRMATION")
        b=stock();b["growth_outlook"]["observed_quarter"]="2026-09-30"
        b["filing_context"]={"status":"CORROBORATED_REPORTED_QUARTER","period":"2026-09-30"}
        q.attach({"status":"RESEARCH_AVAILABLE","stocks":[b],"funds":[]},TODAY)
        self.assertEqual(b["action"],"RESEARCH_FOR_ENTRY")
        b["filing_context"]["audit_opinion"]="QUALIFIED_OPINION"
        self.assertEqual(q.stock(b,TODAY)["state"],"REVIEW_REQUIRED")
