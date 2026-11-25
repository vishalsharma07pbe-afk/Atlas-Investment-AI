import unittest
from datetime import datetime,timezone
from app import release_reconciliation as match
NOW=datetime(2026,11,25,16,tzinfo=timezone.utc)

def fixture():
    row={"id":"one","headline":"Consumer Price Index - October 2026","scheduled_at":"2026-11-25T13:30:00+00:00",
         "status":"SCHEDULE_TIME_PASSED_RELEASE_UNVERIFIED"}
    headline={"id":"a","headline":"CPI announcement","status":"PUBLISHED_FEED_HEADLINE",
              "source_name":"US Bureau of Labor Statistics","geography":"US","feed_ids":["BLS_CPI"],
              "source_url":"https://www.bls.gov/news.release/archives/cpi_11252026.htm","published_at":"2026-11-25T13:30:00+00:00"}
    return {"enabled":True,"economic_calendar":{"status":"CURRENT_SCHEDULE","events":[row]},
            "global_releases":{"sources":[{"source":"BLS_CPI","status":"CURRENT_FEED"}],"events":[headline]}},row,headline

class ReleaseReconciliationTests(unittest.TestCase):
    def test_exact_match_keeps_schedule_status(self):
        snap,row,_=fixture()
        match.attach(snap,NOW)
        self.assertEqual(row["release_match"]["status"],"MATCHED_OFFICIAL_RELEASE_HEADLINE")
        self.assertEqual(row["status"],"SCHEDULE_TIME_PASSED_RELEASE_UNVERIFIED")
    def test_wrong_series_date_time_and_generic_url_not_matched(self):
        for field,value in (("feed_ids",["BLS_PPI"]),("source_url","https://www.bls.gov/news.release/cpi.htm"),
            ("source_url","https://www.bls.gov/news.release/archives/cpi_11242026.htm"),("published_at","2026-11-25T13:29:00+00:00"),
            ("published_at","2026-11-25T17:00:00+00:00")):
            snap,row,e=fixture()
            e[field]=value
            match.attach(snap,NOW)
            self.assertEqual(row["release_match"]["status"],"NO_COMPATIBLE_HEADLINE")
    def test_ambiguity_and_stale_feed(self):
        snap,row,e=fixture()
        snap["economic_calendar"]["events"].append({**row,"id":"two"})
        match.attach(snap,NOW)
        self.assertEqual(row["release_match"]["status"],"AMBIGUOUS_RELEASE_MATCH")
        snap,row,e=fixture()
        snap["global_releases"]["sources"][0]["status"]="STALE_CAPTURE"
        match.attach(snap,NOW)
        self.assertEqual(row["release_match"]["status"],"CURRENT_RELEASE_FEED_UNAVAILABLE")
    def test_upcoming_not_reconciled(self):
        snap,row,_=fixture()
        row["status"]="SCHEDULED"
        match.attach(snap,NOW)
        self.assertNotIn("release_match",row)
