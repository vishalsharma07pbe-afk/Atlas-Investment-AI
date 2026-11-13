import unittest
from datetime import date
from intelligence.app.market_readiness import ReadinessPolicy, evaluate_readiness

TODAY = date(2026, 11, 13)
def healthy():
    return {"instrumentCount": 10, "candleCount": 200, "unresolvedIssueCount": 0,
            "liveMarketDataConnected": True,
            "sources": [{"source_code": "AUTHORIZED", "latest_candle": "2026-11-12"}]}

class MarketReadinessTests(unittest.TestCase):
    def test_healthy_evidence(self):
        result = evaluate_readiness(healthy(), ReadinessPolicy(), TODAY)
        self.assertEqual(result["status"], "READY")
        self.assertTrue(result["research_signals_enabled"])
        self.assertEqual(result["source_age_calendar_days"], 1)

    def test_missing_feed_blocks(self):
        payload = healthy()
        payload["liveMarketDataConnected"] = False
        result = evaluate_readiness(payload, ReadinessPolicy(), TODAY)
        self.assertIn("VERIFIED_LIVE_FEED_UNAVAILABLE", result["blockers"])

    def test_stale_and_quality_events_block(self):
        payload = healthy()
        payload["sources"][0]["latest_candle"] = "2026-10-01"
        payload["unresolvedIssueCount"] = 2
        result = evaluate_readiness(payload, ReadinessPolicy(), TODAY)
        self.assertIn("STALE_MARKET_DATA", result["blockers"])
        self.assertIn("UNRESOLVED_OR_UNKNOWN_QUALITY_EVENTS", result["blockers"])

    def test_unknown_and_future_evidence_fail_closed(self):
        result = evaluate_readiness({"sources": [{"latest_candle": "2026-12-01"}]}, ReadinessPolicy(), TODAY)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("FUTURE_DATED_SOURCE", result["blockers"])
        self.assertIn("NO_DATED_SOURCE_EVIDENCE", result["blockers"])

    def test_manual_only_blocks_default_policy(self):
        payload = healthy()
        payload["liveMarketDataConnected"] = False
        self.assertEqual(evaluate_readiness(payload, ReadinessPolicy(), TODAY)["status"], "BLOCKED")
        self.assertEqual(evaluate_readiness(payload, ReadinessPolicy(require_live_feed=False), TODAY)["status"], "READY")

if __name__ == "__main__":
    unittest.main()
