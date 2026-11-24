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

if __name__=="__main__":
    unittest.main()
