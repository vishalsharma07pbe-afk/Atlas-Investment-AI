import unittest
from datetime import date,timedelta
from app.research_coverage import CoverageRequest,coverage
from app.broker_research import SOURCES

def item(source,days):
    return {"source":source,"instrument_id":"INE848E01016","symbol":"EXAMPLE",
        "published_on":(date.today()-timedelta(days=days)).isoformat(),
        "rating":"BUY","report_url":"https://example.org/report",
        "report_title":"Illustrative submitted research","report_id":source+str(days)}

class CoverageTests(unittest.TestCase):
    def test_fresh_stale_and_missing_are_distinct(self):
        result=coverage(CoverageRequest(instrument_id="INE848E01016",max_age_days=30,
            records=[item("GROWW",1),item("UPSTOX",90)]))
        by_source={p["source"]:p for p in result["providers"]}
        self.assertEqual(by_source["GROWW"]["coverage"],"FRESH_USER_SUBMITTED")
        self.assertEqual(by_source["UPSTOX"]["coverage"],"STALE_USER_SUBMITTED")
        self.assertEqual(by_source["ZERODHA"]["coverage"],"NO_REPORTS_SUPPLIED")
        self.assertEqual(result["fresh_provider_count"],1)
        self.assertEqual(len(result["providers"]),len(SOURCES))
        self.assertFalse(any(p["connected_feed"] for p in result["providers"]))

    def test_empty_does_not_claim_any_broker_coverage(self):
        result=coverage(CoverageRequest(instrument_id="INE848E01016",records=[]))
        self.assertEqual(result["fresh_provider_count"],0)
        self.assertTrue(all(p["coverage"]=="NO_REPORTS_SUPPLIED" for p in result["providers"]))

if __name__=="__main__":unittest.main()
