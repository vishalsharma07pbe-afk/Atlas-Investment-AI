import unittest
from datetime import date
from app.portfolio_opportunities import project

TODAY = date(2026, 11, 24)

def equity(isin="INE002A01018", observed="2026-11-23", exchange="NSE"):
    return {"isin":isin,"symbol":"EXAMPLE","exchange":exchange,"as_of":observed,
            "adjustment_status":"RAW_UNADJUSTED",
            "company_evidence":{"isin":isin,"sections":{"profile":{"data":{"sector":"Energy"}}}}}

def market(items, status="READY", gate="TECHNICAL_WATCH_ONLY"):
    return {"section":"NSE","status":status,"result":{"horizons":{"LONG_TERM":{
        "status":gate,"candidates":items,"blockers":["FUNDAMENTALS_NOT_VERIFIED"]}}}}

def fund(items):
    return {"section":"LARGE_CAP","status":"READY","result":{"historical_coverage":{
        "status":"HISTORICAL_WATCH_ONLY","comparison_date":"2026-11-23","items":items}}}

class OpportunityProjectionTests(unittest.TestCase):
    def test_only_current_watches_and_exact_identities(self):
        snapshot={"enabled":True,"sections":[market([equity(),equity(),equity("INE009A01021","2026-11-01"),equity("INVALID")])]}
        result=project(snapshot,TODAY)
        self.assertEqual(len(result["equities"]),1)
        item=result["equities"][0]
        self.assertEqual(item["sector"],"Energy")
        self.assertEqual(item["evidence_type"],"TECHNICAL_WATCH_ONLY")
        self.assertIn("FUNDAMENTALS_NOT_VERIFIED",item["blockers"])

    def test_disabled_stale_and_unqualified_sections(self):
        for snapshot in [{"enabled":False,"sections":[market([equity()])]},
                         {"enabled":True,"sections":[market([equity()],status="STALE")]},
                         {"enabled":True,"sections":[market([equity()],gate="NO_QUALIFIED_EVIDENCE")]}]:
            self.assertFalse(project(snapshot,TODAY)["equities"])

    def test_historical_funds_are_never_recommendations(self):
        row={"scheme_code":123456,"scheme_name":"Example Direct Growth","nav_date":"2026-11-23",
             "cagr_3y_percent":12.5,"drawdown_3y_percent":-20}
        result=project({"enabled":True,"sections":[fund([row,{**row,"scheme_code":123457,"nav_date":"2026-11-20"}])]},TODAY)
        self.assertEqual(len(result["funds"]),1)
        self.assertEqual(result["funds"][0]["evidence_type"],"HISTORICAL_WATCH_ONLY")
        self.assertEqual(result["funds"][0]["scheme_code"],"123456")

    def test_exact_public_price_window_projection(self):
        item={**equity(),"id":1,"adjustment_status":"ADJUSTED"}
        section=market([item])
        section["result"]["discovery_coverage"]={"calendar_status":"PUBLISHED_SESSION","calendar_checked_on":TODAY.isoformat(),"expected_session":item["as_of"]}
        raw={"isin":item["isin"],"id":1,"exchange":"NSE","as_of":item["as_of"],"security_state":"NORMAL",
             "comparative_price_windows":{"60":{"first_date":"2026-08-25","last_date":item["as_of"],"dates_digest":"a"*64,"source_code":"UPSTOX","return_percent":8}}}
        section["result"]["company_research_universe"]=[raw]
        snapshot={"enabled":True,"sections":[section]}
        self.assertEqual(project(snapshot,TODAY)["equities"][0]["matched_60"]["return_percent"],8)
        section["result"]["company_research_universe"]=[raw,raw]
        self.assertIsNone(project(snapshot,TODAY)["equities"][0]["matched_60"])
