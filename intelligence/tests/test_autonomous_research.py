import os
import tempfile
import unittest
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
