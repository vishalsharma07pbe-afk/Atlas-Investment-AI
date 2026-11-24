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
