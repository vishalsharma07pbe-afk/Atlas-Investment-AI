import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import nav_catalog

class NavHistoryTests(unittest.TestCase):
    def test_history_dedup_audit_and_return(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(nav_catalog, "DB_PATH", Path(folder) / "nav.sqlite3"):
                a = "123456;INF000A;INF000B;Example Fund;10.00;01-Nov-2026"
                b = "123456;INF000A;INF000B;Example Fund;11.00;02-Nov-2026"
                first = nav_catalog.import_snapshot(a)
                again = nav_catalog.import_snapshot(a)
                latest = nav_catalog.import_snapshot(b)
                self.assertEqual(first["inserted_history_rows"], 1)
                self.assertEqual(again["inserted_history_rows"], 0)
                self.assertEqual(latest["inserted_history_rows"], 1)
                history = nav_catalog.scheme_history(123456)
                self.assertEqual(len(history["items"]), 2)
                self.assertEqual(history["observed_period_return_percent"], "10.0")
                self.assertIsNone(history["verified_rating"])
                self.assertEqual(len(nav_catalog.import_audit()["items"]), 3)
    def test_limits(self):
        with self.assertRaises(ValueError):
            nav_catalog.scheme_history(0)
        with self.assertRaises(ValueError):
            nav_catalog.import_audit(101)
if __name__ == "__main__":
    unittest.main()
