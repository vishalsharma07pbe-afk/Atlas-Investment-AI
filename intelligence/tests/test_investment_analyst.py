import unittest
from datetime import date
from app import investment_analyst as a

TODAY=date(2026,11,28)
def snapshot():
    r={"id":1,"isin":"INE002A01018","symbol":"RELIANCE","exchange":"NSE","as_of":"2026-11-27",
       "close":100,"atr_percent":2,"adjustment_status":"ADJUSTED","reasons":["Positive momentum"]}
    return {"enabled":True,"scope":"PUBLIC_MARKET_RESEARCH_ONLY","research_date":TODAY.isoformat(),"sections":[
        {"section":"NSE","status":"READY","result":{"discovery_coverage":{"calendar_checked_on":TODAY.isoformat(),
        "calendar_status":"PUBLISHED_SESSION","expected_session":"2026-11-27"},"horizons":{"SWING":{"status":"TECHNICAL_WATCH_ONLY","candidates":[r]}}}}]}
def fund():
    return {"section":"LARGE_CAP","status":"READY","result":{"category":"LARGE_CAP",
      "historical_research_shortlist":{"methodology":"MF-MATCHED-PEER-1","status":"HISTORICAL_SHORTLIST_AVAILABLE","category":"LARGE_CAP",
        "last_date":"2026-11-27","items":[{"identifier":"123456","name":"Fund A","nav_date":"2026-11-27","qualified":False,"status":"HISTORICAL_RESEARCH_ONLY","score":85,"weekly_cagr_percent":12}]},
      "growth_driver_review":{"methodology":"MF-QUARTERLY-DRIVERS-1","items":[{"identifier":"123456","qualified":False,"nav_date":"2026-11-27",
      "portfolio_date":"2026-10-31","quarter":"2026-09-30","joint_coverage_weight_percent":80,"joint_growth_weight_percent":65,"review_weight_percent":5,"state":"POSITIVE_HISTORICAL_DRIVERS_ONLY"}]}}}
class AnalystTest(unittest.TestCase):
    def test_current_technical_fallback_and_risk_scenario(self):
        s=snapshot()
        r=a.analyze(s,TODAY)
        pick=r["stocks"][0]
        self.assertEqual(pick["tier"],"TECHNICAL_LEAD")
        self.assertFalse(pick["qualified"])
        self.assertEqual(pick["price_plan"]["stop_scenario"],96)
        self.assertEqual(pick["price_plan"]["target_scenario"],108)
        row=s["sections"][0]["result"]["horizons"]["SWING"]["candidates"][0]
        row["adjustment_status"]="RAW_UNADJUSTED"
        self.assertIsNone(a.analyze(s,TODAY)["stocks"][0]["price_plan"])
        row["governance_review"]={"findings":["REVIEW"]}
        self.assertEqual(a.analyze(s,TODAY)["stocks"],[])
    def test_fund_driver_join_does_not_certify(self):
        s=snapshot();s["sections"].append(fund())
        p=a.analyze(s,TODAY)["funds"][0]["items"][0]
        self.assertEqual(p["tier"],"DRIVER_SUPPORTED")
        self.assertFalse(p["qualified"])
        d=s["sections"][1]["result"]["growth_driver_review"]["items"][0]
        d["review_weight_percent"]=25
        self.assertEqual(a.analyze(s,TODAY)["funds"][0]["items"][0]["tier"],"DRIVER_REVIEW")
        d["nav_date"]="2026-11-26"
        self.assertEqual(a.analyze(s,TODAY)["funds"][0]["items"][0]["tier"],"HISTORICAL_ONLY")
    def test_stale_and_disabled_not_reused(self):
        s=snapshot();s["sections"].append(fund());s["research_date"]="2026-11-27"
        self.assertEqual(a.analyze(s,TODAY)["stocks"],[])
        self.assertEqual(a.analyze(s,TODAY)["funds"],[])
        s["enabled"]=False
        self.assertEqual(a.analyze(s,TODAY)["status"],"DISABLED")

    def test_alternate_strategy_plan_requires_validated_geometry(self):
        s=snapshot()
        row={"id":1,"isin":"INE002A01018","symbol":"RELIANCE","exchange":"NSE","as_of":"2026-11-27",
             "close":100,"qualified":False,"adjustment_verified_for_screen":True,
             "strategies":["TURTLE_LONG_BREAKOUT"],"families":["MOMENTUM"],"observed_facts":{},
             "price_plan":{"reference":100,"stop_scenario":96,"target_scenario":108,"reward_risk":2,
                           "method":"STRATEGY_RISK_GEOMETRY_V1","strategy":"TURTLE_LONG_BREAKOUT",
                           "qualified":False,"notice":"Illustrative scenario"}}
        s["multi_strategy"]={"methodology":"MULTI-STRATEGY-1","items":[row]}
        pick=a.analyze(s,TODAY)["stocks"][0]
        self.assertEqual(pick["tier"],"MULTI_STRATEGY_RESEARCH")
        self.assertEqual(pick["price_plan"]["stop_scenario"],96)
        self.assertFalse(pick["qualified"])
        row["adjustment_verified_for_screen"]=False
        self.assertIsNone(a.analyze(s,TODAY)["stocks"][0]["price_plan"])
        row["as_of"]="2026-11-26"
        self.assertEqual(a.analyze(s,TODAY)["stocks"][0]["tier"],"TECHNICAL_LEAD")
        row["as_of"]="2026-11-27"
        row["adjustment_verified_for_screen"]=True
        row["price_plan"]["reward_risk"]=None
        self.assertIsNone(a.analyze(s,TODAY)["stocks"][0]["price_plan"])
