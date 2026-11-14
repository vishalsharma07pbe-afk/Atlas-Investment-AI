import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from app import reliability_incidents as incidents

class ReliabilityIncidentTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.patch = patch.object(incidents, "DB_PATH", Path(self.folder.name) / "incidents.sqlite3")
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.folder.cleanup()

    def test_observation_deduplicates_and_resolves(self):
        issue = [{"dataset": "GLOBAL_NEWS", "code": "MISSING"}]
        incidents.record_snapshot(issue)
        incidents.record_snapshot(issue)
        state = incidents.history()
        self.assertEqual(state["open_count"], 1)
        self.assertEqual(state["incidents"][0]["occurrences"], 2)
        incidents.record_snapshot([])
        state = incidents.history()
        self.assertEqual(state["open_count"], 0)
        self.assertEqual(state["incidents"][0]["state"], "RESOLVED")
        self.assertFalse(state["live_feed_connected"])

    def test_reappearing_issue_reopens(self):
        issue = [{"dataset": "MARKET_DATA", "code": "UNVERIFIED_SOURCE"}]
        incidents.record_snapshot(issue)
        incidents.record_snapshot([])
        incidents.record_snapshot(issue)
        self.assertEqual(incidents.history()["incidents"][0]["occurrences"], 2)
        self.assertEqual(incidents.history()["incidents"][0]["state"], "OPEN")

    def test_reject_invalid_and_preserve_existing(self):
        incidents.record_snapshot([{"dataset": "NAV", "code": "STALE"}])
        for bad in [[{"dataset": "NAV", "code": "UNKNOWN"}],
                    [{"dataset": "a' OR 1=1", "code": "STALE"}],
                    [{"dataset": "NAV", "code": "STALE"}] * 101,
                    "bad"]:
            with self.assertRaises(ValueError):
                incidents.record_snapshot(bad)
        self.assertEqual(incidents.history()["open_count"], 1)
        with self.assertRaises(ValueError):
            incidents.history(101)

if __name__ == "__main__":
    unittest.main()
