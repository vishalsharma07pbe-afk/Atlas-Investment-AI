import unittest
from datetime import date
from app import unified_decision as d, stock_qualification, elite_assessment

TODAY=date(2026,11,27)
ISIN="INE002A01018"
def fixture():
    gate={"methodology":stock_qualification.VERSION,"status":"WITHHELD_EVIDENCE_GAPS","horizon":"SWING",
          "blockers":["FINAL_QUALIFICATION_VALIDATION_REQUIRED"],"review_findings":[]}
    item={"isin":ISIN,"id":1,"symbol":"TEST","exchange":"NSE","as_of":"2026-11-26","stock_qualification":gate}
    group={"status":"TECHNICAL_WATCH_ONLY","candidates":[item]}
    section={"section":"NSE","status":"READY","result":{"discovery_coverage":{"calendar_checked_on":TODAY.isoformat(),"calendar_status":"PUBLISHED_SESSION","expected_session":"2026-11-26"},"horizons":{"SWING":group}}}
    return {"scope":"PUBLIC_MARKET_RESEARCH_ONLY","enabled":True,"research_date":TODAY.isoformat(),"sections":[section],
        "stock_qualification":{"horizons":{"SWING":{"qualified_count":0,"selection":{"watch_refs":[{"isin":ISIN,"id":1,"exchange":"NSE"}]}}}}},item

class UnifiedDecisionTests(unittest.TestCase):
    def test_selection_and_ai_conflict_never_qualify(self):
        snapshot,item=fixture()
        item["ai_review"]={"company_isin":ISIN,"committee":{"reviewed_count":2,"claim_comparison":{"status":"CONFLICTING_ASSERTIONS"}}}
        result=d.summarize(snapshot,TODAY)
        self.assertEqual(result["equity_company_count"],1)
        self.assertEqual(result["equity_review_count"],1)
        self.assertFalse(result["equity_companies"][0]["qualified"])
        self.assertEqual(result["ai_reviewed_company_count"],1)
        snapshot["stock_qualification"]["horizons"]["SWING"]["selection"]["watch_refs"]=[]
        self.assertEqual(d.summarize(snapshot,TODAY)["equity_companies"],[])
    def test_missing_final_gate_or_stale_scope_not_promoted(self):
        snapshot,item=fixture()
        item["stock_qualification"]["blockers"]=[]
        self.assertFalse(d.summarize(snapshot,TODAY)["equity_companies"])
        snapshot["research_date"]="2026-11-26"
        self.assertIsNone(d.summarize(snapshot,TODAY)["equity_company_count"])
    def test_exact_fund_historical_match_preserves_blockers(self):
        snapshot,_=fixture()
        fund={"identifier":"123456","name":"Example","category":"LARGE_CAP","nav_date":"2026-11-26",
              "top_performer":{"status":"WITHHELD","missing":["TRI_MISSING"]},
              "growth_outlook":{"status":"WITHHELD","missing":["FORWARD_EVIDENCE_MISSING"]}}
        result={"category":"LARGE_CAP","research_reports":[fund],"historical_research_shortlist":{"status":"HISTORICAL_SHORTLIST_AVAILABLE","category":"LARGE_CAP","items":[{"identifier":"123456","nav_date":"2026-11-26","qualified":False,"status":"HISTORICAL_RESEARCH_ONLY"}]}}
        snapshot["sections"].append({"section":"LARGE_CAP","status":"READY","result":result})
        row=d.summarize(snapshot,TODAY)["fund_categories"][0]
        self.assertEqual(row["growth_withheld_count"],1)
        self.assertFalse(row["historical_watches"][0]["qualified"])
        result["research_reports"].append(fund)
        self.assertFalse(d.summarize(snapshot,TODAY)["fund_categories"][0]["historical_watches"])

    def test_elite_and_daily_watches_count_one_company(self):
        snapshot,item=fixture()
        elite={**item,"status":"SCREEN_MATCH_ONLY","elite_assessment":{"methodology":elite_assessment.VERSION,
          "status":"SCORE_WITHHELD","qualified":False,"blockers":["FINAL_QUALIFICATION_VALIDATION_REQUIRED"]}}
        snapshot["steady_momentum"]={"items":[elite],"category_items":{"LARGE_CAP":[elite]}}
        result=d.summarize(snapshot,TODAY)
        self.assertEqual(result["equity_company_count"],1)
        self.assertEqual(len(result["equity_companies"][0]["observations"]),2)
