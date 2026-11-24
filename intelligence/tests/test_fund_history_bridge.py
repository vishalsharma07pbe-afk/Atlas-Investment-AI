import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import mutual_fund_recommendations as mf, nav_catalog
from app.market_client import _internal_path

class FundHistoryBridgeTests(unittest.TestCase):
    def test_verified_history_coverage_does_not_unlock_recommendations(self):
        with tempfile.TemporaryDirectory() as root, patch.object(nav_catalog,"DB_PATH",Path(root)/"fund.sqlite"), patch.object(mf,"backend_json",return_value={"category":"LARGE_CAP","universe_count":20,"eligible_count":5,"sample_count":10,"items":[],"status":"HISTORICAL_WATCH_ONLY","comparison_date":"2026-11-23","weekly_risk_eligible_count":4}):
            result=mf.dashboard("LARGE_CAP")
        self.assertEqual(result["coverage"]["official_category_verified"],20)
        self.assertEqual(result["coverage"]["dated_nav_history_eligible"],5)
        self.assertEqual(result["top_performers"],[])
        self.assertEqual(result["growth_outlook"],[])
        self.assertIn("BENCHMARK_TRI_NOT_CONNECTED",result["blockers"])
        self.assertIn("EXPENSE_RATIO_NOT_CONNECTED",result["blockers"])
        self.assertNotIn("OFFICIAL_CATEGORY_SOURCE_NOT_CONNECTED",result["blockers"])

    def test_only_supported_category_route(self):
        self.assertEqual(_internal_path("/api/v1/mutual-funds/historical-watch?category=INDEX"),"/api/v1/internal/feed/fund-history?category=INDEX")
