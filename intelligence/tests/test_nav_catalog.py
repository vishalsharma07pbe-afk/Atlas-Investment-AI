import os
import tempfile
import unittest
from unittest.mock import patch

from app import nav_catalog

SAMPLE = """Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date
Test Mutual Fund
123456;INF000000001;-;Example Direct Growth;123.4500;13-Nov-2026
123457;INF000000002;-;Example Index Fund;10.5;12-Nov-2026
123458;INF000000003;-;Invalid NAV;NaN;12-Nov-2026
"""

class NavCatalogTests(unittest.TestCase):
    def test_parse_and_reject_invalid(self):
        rows, invalid = nav_catalog.parse_nav(SAMPLE)
        self.assertEqual(len(rows), 2)
        self.assertEqual(invalid, 1)
        self.assertEqual(rows[0][2], "123.4500")

    def test_empty_and_oversize_rejected(self):
        with self.assertRaisesRegex(ValueError, "NO_VALID_NAV_RECORDS"):
            nav_catalog.parse_nav("garbage")
        with self.assertRaisesRegex(ValueError, "NAV_FILE_TOO_LARGE"):
            nav_catalog.parse_nav("x" * (nav_catalog.MAX_BYTES + 1))

    def test_future_date_and_duplicate_rejected(self):
        rows, invalid = nav_catalog.parse_nav(
            "1;-;-;Future Fund;10;31-Dec-2099\n2;-;-;Valid Fund;10;12-Nov-2026\n2;-;-;Duplicate;11;12-Nov-2026")
        self.assertEqual(len(rows), 1)
        self.assertEqual(invalid, 2)

    def test_persistent_search_and_old_snapshot_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(nav_catalog, "DB_PATH", nav_catalog.Path(folder) / "nav.sqlite3"):
                result = nav_catalog.import_snapshot(SAMPLE)
                self.assertEqual(result["parsed"], 2)
                found = nav_catalog.search_schemes("Example")
                self.assertEqual(len(found["items"]), 2)
                self.assertFalse(found["live_feed_connected"])
                nav_catalog.import_snapshot("123456;-;-;Example Direct Growth;1;01-Jan-2020")
                found = nav_catalog.search_schemes("123456")
                self.assertEqual(found["items"][0]["nav"], "123.4500")
                self.assertEqual(nav_catalog.catalog_status()["scheme_count"], 2)
                self.assertFalse(nav_catalog.catalog_status()["automatic_collection_enabled"])

    def test_literal_search_wildcards(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(nav_catalog, "DB_PATH", nav_catalog.Path(folder) / "nav.sqlite3"):
                nav_catalog.import_snapshot(SAMPLE)
                self.assertEqual(nav_catalog.search_schemes("%")["items"], [])

if __name__ == "__main__":
    unittest.main()
