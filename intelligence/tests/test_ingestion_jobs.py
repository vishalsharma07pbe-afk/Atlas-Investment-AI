import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import ingestion_jobs as jobs

class IngestionLedgerTests(unittest.TestCase):
    def test_dedup_retry_and_success(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(jobs, "DB_PATH", Path(directory) / "jobs.sqlite3"):
            a = jobs.enqueue("NAV_IMPORT", "manual-file-1", "nav-1")
            self.assertEqual(a["id"], jobs.enqueue("NAV_IMPORT", "manual-file-1", "nav-1")["id"])
            with self.assertRaises(ValueError):
                jobs.enqueue("NAV_IMPORT", "manual-file-2", "nav-1")
            running = jobs.claim(a["id"])
            self.assertEqual(running["attempts"], 1)
            retry = jobs.finish(a["id"], False, "SOURCE_UNAVAILABLE")
            self.assertEqual(retry["status"], "RETRY")
            with self.assertRaises(ValueError):
                jobs.claim(a["id"])
            self.assertEqual(jobs.status()["jobs"][0]["last_error"], "SOURCE_UNAVAILABLE")
    def test_reject_credentials_and_invalid_state(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(jobs, "DB_PATH", Path(directory) / "jobs.sqlite3"):
            with self.assertRaises(ValueError):
                jobs.enqueue("NAV_IMPORT", "access_token=secret", "unsafe")
            with self.assertRaises(ValueError):
                jobs.enqueue("UNSUPPORTED", "ref", "key")
            a = jobs.enqueue("OHLCV_IMPORT", "fixture", "unique")
            with self.assertRaises(ValueError):
                jobs.finish(a["id"], True)
            jobs.claim(a["id"])
            self.assertEqual(jobs.finish(a["id"], True)["status"], "SUCCEEDED")
if __name__ == "__main__":
    unittest.main()
