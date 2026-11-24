import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app import autonomous_research as research


class AutonomousResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"ATLAS_RESEARCH_SNAPSHOT_DB": self.temp.name + "/research.sqlite3",
            "ATLAS_AUTONOMOUS_RESEARCH_ENABLED": "true"})
        self.env.start()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.env.stop)

    def test_pending_then_persisted_sections(self):
        self.assertTrue(all(row["status"] == "PENDING" for row in research.read_snapshot()["sections"]))
        research.refresh_once(lambda exchange: {"eligible_count": 1, "exchange": exchange},
                              lambda category: {"category": category, "growth_outlook": []})
        snapshot = research.read_snapshot()
        self.assertEqual(len(snapshot["sections"]), 7)
        self.assertTrue(all(row["status"] == "READY" for row in snapshot["sections"]))
        self.assertEqual(snapshot["sections"][0]["result"]["exchange"], "NSE")

    def test_failure_retains_last_good_but_marks_failed(self):
        research.refresh_once(lambda exchange: {"exchange": exchange}, lambda category: {"category": category})
        def failed(exchange):
            raise RuntimeError("private-token-must-not-leak")
        research.refresh_once(failed, lambda category: {"category": category})
        sections = research.read_snapshot()["sections"]
        self.assertEqual(sections[0]["status"], "FAILED")
        self.assertEqual(sections[0]["result"]["exchange"], "NSE")
        self.assertNotIn("private-token", str(sections))
        self.assertEqual(sections[2]["status"], "READY")

    def test_invalid_interval_disables_scheduler(self):
        with patch.dict(os.environ, {"ATLAS_AUTONOMOUS_RESEARCH_INTERVAL_SECONDS": "1"}):
            self.assertFalse(research.config()[0])

    def test_recent_snapshot_with_expired_observation_is_stale(self):
        before = datetime(2026, 11, 24, 18, 0, tzinfo=timezone.utc)
        after = datetime(2026, 11, 24, 19, 0, tzinfo=timezone.utc)
        with patch.object(research, "now", return_value=before):
            research.refresh_once(
                lambda exchange: {"momentum_leaders": [{"as_of": "2026-11-20"}]},
                lambda category: {"historical_coverage": {"comparison_date": "2026-11-17",
                    "items": [{"nav_date": "2026-11-17"}]}})
            self.assertTrue(all(r["status"] == "READY" for r in research.read_snapshot(False)["sections"]))
        with patch.object(research, "now", return_value=after):
            sections = research.read_snapshot(False)["sections"]
            self.assertTrue(all(r["status"] == "STALE" for r in sections))
            self.assertTrue(all(r["error_code"] == "UNDERLYING_OBSERVATION_STALE" for r in sections))
            self.assertTrue(all(r["result"] is not None for r in sections))

    def test_corrupt_section_does_not_break_other_sections(self):
        research.refresh_once(lambda exchange: {"exchange": exchange}, lambda category: {"category": category})
        from contextlib import closing
        with closing(research._connect()) as db, db:
            db.execute("UPDATE research_sections SET payload=? WHERE section='NSE'", ("not-json",))
        rows = research.read_snapshot(False)["sections"]
        self.assertEqual(rows[0]["status"], "FAILED")
        self.assertIsNone(rows[0]["result"])
        self.assertEqual(rows[0]["error_code"], "INVALID_STORED_RESEARCH_SNAPSHOT")
        self.assertTrue(all(r["status"] == "READY" for r in rows[1:]))

    def test_disabled_scheduler_does_not_label_old_results_ready(self):
        research.refresh_once(lambda exchange: {"exchange": exchange}, lambda category: {"category": category})
        with patch.dict(os.environ, {"ATLAS_AUTONOMOUS_RESEARCH_ENABLED": "false"}):
            self.assertTrue(all(r["status"] == "DISABLED" for r in research.read_snapshot(False)["sections"]))

    def test_expanded_discovery_uses_bounded_batches_and_existing_screener(self):
        from urllib.parse import parse_qs, urlsplit
        from datetime import date, timedelta
        instruments=[{"id":i,"exchange":"NSE","symbol":f"T{i}","active":True,
                      "listing_status":"ACTIVE","series":"EQ","instrument_type":"EQ",
                      "recent_registry_count":230} for i in range(1,201)]
        calls=[]
        def load(path):
            calls.append(path)
            if "discovery-universe?" in path:
                return instruments
            ids=[int(i) for i in parse_qs(urlsplit(path).query)["ids"]]
            self.assertLessEqual(len(ids),20)
            return [{"instrument_id":i,"trade_date":(date(2026,10,31)+timedelta(days=d)).isoformat(),
                     "open":100+d,"high":102+d,"low":99+d,"close":101+d,"volume":100000,
                     "adjustment_status":"RAW_UNADJUSTED"} for i in ids for d in range(24)]
        with patch.object(research,"now",return_value=datetime(2026,11,24,12,tzinfo=timezone.utc)), \
             patch.object(research,"backend_json",side_effect=load):
            result=research.market_snapshot("NSE")
        self.assertEqual(result["eligible_count"],200)
        self.assertEqual(result["universe_size"],200)
        self.assertEqual(result["discovery_coverage"]["recent_registry_count"],230)
        self.assertEqual(len(calls),11)
        self.assertEqual(len(result["top_gainers"]),5)

    def test_batch_rejects_unrequested_history(self):
        row={"id":1,"exchange":"NSE","symbol":"TEST","active":True,"listing_status":"ACTIVE",
             "series":"EQ","instrument_type":"EQ","recent_registry_count":1}
        with patch.object(research,"backend_json",side_effect=[[row],[{"instrument_id":2}]]):
            with self.assertRaisesRegex(ValueError,"IDENTITY_MISMATCH"):
                research.market_snapshot("NSE")

    def test_published_calendar_assertion_expires_at_ist_date_rollover(self):
        result={"discovery_coverage":{"expected_session":"2026-11-23","calendar_checked_on":"2026-11-24"},
                "top_gainers":[{"as_of":"2026-11-23"}]}
        from datetime import date
        self.assertTrue(research._published_evidence_current("NSE",result,date(2026,11,24)))
        self.assertFalse(research._published_evidence_current("NSE",result,date(2026,11,25)))
        result["top_gainers"][0]["as_of"]="2026-11-22"
        self.assertFalse(research._published_evidence_current("NSE",result,date(2026,11,24)))
