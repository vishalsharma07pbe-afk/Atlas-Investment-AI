import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


def candle_payload(count=220):
    start = date(2025, 1, 1)
    return {"candles": [
        {"trade_date": (start + timedelta(days=index)).isoformat(),
         "close": 100 + index * 0.25 + (index % 5),
         "adjustment_status": "RAW_UNADJUSTED"}
        for index in range(count)
    ]}


class P2ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_grounded_research_response_has_citations_and_uncertainty(self):
        response = self.client.post("/api/v1/intelligence/p2/research/answer", json={
            "question": "What does the verified trend show?",
            "asset_name": "TEST",
            "asset_type": "STOCK",
            "use_ai": False,
            "evidence": [{
                "id": "TREND",
                "domain": "TECHNICALS",
                "statement": "The validated daily trend is rising.",
                "source_name": "ATLAS validated daily OHLCV",
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "quality": "VERIFIED",
            }],
        })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["findings"][0]["evidence_ids"], ["TREND"])
        self.assertIn("FUNDAMENTALS", body["coverage"]["missing_expected_domains"])

    def test_walk_forward_route_uses_backend_candles(self):
        with patch("app.main.backend_json", return_value=candle_payload()):
            response = self.client.get(
                "/api/v1/intelligence/p2/backtest/7?lookback=10&train_size=80&test_size=10"
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "WALK_FORWARD_RESEARCH_ONLY")
        self.assertIn("TRAIN_WINDOW_PRECEDES_TEST_WINDOW", body["leakage_controls"])

    def test_screener_fails_closed_when_required_factor_is_missing(self):
        response = self.client.post("/api/v1/intelligence/p2/screener/evaluate", json={
            "candidates": [{
                "id": 7, "symbol": "TEST", "exchange": "NSE", "as_of": "2026-11-18",
                "momentum_20d_percent": 8.0, "roe_percent": None,
            }],
            "min_momentum_percent": 5,
            "min_roe_percent": 10,
        })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["matched_count"], 0)
        self.assertIn("roe_percent", body["excluded"][0]["missing_required_factors"])

    def test_planning_route_returns_explicit_scenarios(self):
        response = self.client.post("/api/v1/intelligence/p2/planning", json={
            "target_amount": "2500000", "initial_amount": "100000",
            "monthly_contribution": "15000", "years": 7,
            "assumed_return_percent": "8", "inflation_percent": "5",
            "estimated_tax_drag_percent": "1", "emergency_months": 6,
            "income_stability": 3, "loss_tolerance": 3, "horizon_tolerance": 3,
        })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual([row["name"] for row in body["scenarios"]],
                         ["STRESS", "BASE_ASSUMPTION", "FAVOURABLE"])
        self.assertIn("not forecasts", body["notice"].lower())


if __name__ == "__main__":
    unittest.main()
