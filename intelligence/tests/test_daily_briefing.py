import unittest
from app.daily_briefing import summarize


class DailyBriefingTests(unittest.TestCase):
    def test_current_evidence_and_unavailable_qualification_are_distinct(self):
        snapshot={"enabled":True,"sections":[
            {"section":"NSE","status":"READY","result":{"eligible_count":10,"universe_size":20,"horizons":{
                "SWING":{"status":"TECHNICAL_WATCH_ONLY","candidates":[
                    {"id":1,"exchange":"NSE","ai_review":{"reviews":[{"provider":"OLLAMA"}]},
                     "research_reliability":{"status":"REVIEW_CONFLICTING_EVIDENCE","blockers":["VALUATION_NOT_VERIFIED"]}}]}}}},
            {"section":"BSE","status":"STALE","result":{"eligible_count":99,"universe_size":99}},
            {"section":"LARGE_CAP","status":"READY","result":{"growth_outlook":[],"historical_coverage":{
                "status":"HISTORICAL_WATCH_ONLY","items":[{"scheme_code":1}]}}}],
            "institutional_activity":{"status":"RECENT_PROVIDER_EVIDENCE","paired_five_date_window":{
                "dates":["2026-11-17","2026-11-18","2026-11-19","2026-11-20","2026-11-23"],
                "fii_net":"-10","dii_net":"15"}}}
        result=summarize(snapshot)
        self.assertEqual(result["status"],"PARTIAL")
        self.assertEqual(result["market"]["eligible_histories"],10)
        self.assertEqual(result["horizons"]["SWING"]["displayed_watch_count"],1)
        self.assertEqual(result["horizons"]["SWING"]["ai_reviewed_count"],1)
        self.assertEqual(result["horizons"]["SWING"]["conflicting_evidence_count"],1)
        self.assertIsNone(result["horizons"]["SWING"]["qualified_count"])
        self.assertEqual(result["funds"]["growth_pick_count"],0)
        self.assertEqual(result["funds"]["historical_watch_count"],1)
        self.assertEqual(result["institutional"]["fii_direction"],"NET_SELLING")
        self.assertEqual(result["leading_evidence_gaps"],[{"code":"VALUATION_NOT_VERIFIED","watch_count":1}])

    def test_missing_and_disabled_sections_do_not_look_qualified(self):
        for enabled in (True,False):
            result=summarize({"enabled":enabled,"sections":[{"section":"NSE","status":"STALE","result":{}}]})
            self.assertEqual(result["ready_sections"],0)
            self.assertIsNone(result["funds"]["growth_pick_count"])
            self.assertIsNone(result["horizons"]["LONG_TERM"]["qualified_count"])
            self.assertEqual(result["institutional"]["status"],"UNAVAILABLE")

    def test_disabled_snapshot_does_not_count_retained_ready_data(self):
        result=summarize({"enabled":False,"sections":[{"section":"NSE","status":"READY","result":{"eligible_count":7}}]})
        self.assertEqual(result["market"]["eligible_histories"],0)
        self.assertEqual(result["status"],"DISABLED")

    def test_canonical_watches_and_review_union_exclude_stale_venues(self):
        isin="INE009A01021"
        row={"id":1,"exchange":"NSE","isin":isin,"symbol":"TEST","as_of":"2026-11-23",
             "stock_qualification":{"status":"WITHHELD_REVIEW_REQUIRED","review_findings":["REPLAY_REVIEW"],"blockers":["VALUATION"]},
             "selection_company_context":{"review_findings":["OWNERSHIP_REVIEW"],"blockers":["OWNERSHIP","VALUATION"]}}
        ref={"exchange":"NSE","id":1,"isin":isin}
        stale={**row,"id":2,"exchange":"BSE"}
        assessment={"status":"NO_QUALIFIED_IN_REVIEWED_SAMPLE","qualified_count":0,
                    "selection":{"watch_refs":[ref,ref,{"exchange":"BSE","id":2,"isin":isin}]}}
        group={"status":"TECHNICAL_WATCH_ONLY","candidates":[row]}
        snapshot={"enabled":True,"sections":[
            {"section":"NSE","status":"READY","result":{"horizons":{"SWING":group,"LONG_TERM":group}}},
            {"section":"BSE","status":"STALE","result":{"horizons":{"SWING":{"status":"TECHNICAL_WATCH_ONLY","candidates":[stale]}}}}],
            "stock_qualification":{"horizons":{"SWING":assessment,"LONG_TERM":assessment}},
            "market_regime":{"status":"OBSERVED_BENCHMARK_REGIME","as_of":"2026-11-23","trend":"RISING"},
            "global_context":{"available_count":3,"total_count":8}}
        result=summarize(snapshot)["decision_context"]
        self.assertEqual(len(result["horizons"]["SWING"]["selected_watches"]),1)
        self.assertEqual(result["horizons"]["SWING"]["qualified_count"],0)
        self.assertEqual(result["horizons"]["SWING"]["selected_watches"][0]["unresolved_requirement_count"],2)
        self.assertEqual(result["review_company_count"],1)
        self.assertEqual(result["review_companies"][0]["findings"],["OWNERSHIP_REVIEW","REPLAY_REVIEW"])
        self.assertEqual(result["review_companies"][0]["horizons"],["SWING","LONG_TERM"])
        self.assertEqual(result["regime"]["trend"],"RISING")
        self.assertEqual(result["global_coverage"]["available_count"],3)
        snapshot["enabled"]=False
        disabled=summarize(snapshot)["decision_context"]
        self.assertEqual(disabled["horizons"],{})
        self.assertEqual(disabled["review_companies"],[])
        self.assertEqual(disabled["regime"]["status"],"UNAVAILABLE")
        self.assertIsNone(disabled["global_coverage"])

if __name__=="__main__":
    unittest.main()
