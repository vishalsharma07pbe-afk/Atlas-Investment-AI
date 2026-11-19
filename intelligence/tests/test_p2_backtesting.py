import unittest
from datetime import date, timedelta

from app.p2_backtesting import walk_forward


def candles(count=240):
    start = date(2025, 1, 1)
    rows = []
    price = 100.0
    for index in range(count):
        price *= 1 + (0.003 if index % 9 < 6 else -0.002)
        rows.append({"trade_date": (start + timedelta(days=index)).isoformat(),
                     "close": price, "adjustment_status": "RAW_UNADJUSTED"})
    return {"candles": rows}


class WalkForwardTests(unittest.TestCase):
    def test_uses_strictly_earlier_training_windows(self):
        result = walk_forward(candles(), lookback=20, train_size=100, test_size=20)
        self.assertEqual(result["status"], "WALK_FORWARD_RESEARCH_ONLY")
        self.assertGreater(result["observations"], 0)
        for fold in result["folds"]:
            self.assertLess(fold["train_to"], fold["test_from"])
        self.assertIn("NEXT_SESSION_OUTCOME", result["leakage_controls"])

    def test_rejects_mixed_adjustment_series(self):
        payload = candles()
        payload["candles"][-1]["adjustment_status"] = "ADJUSTED"
        with self.assertRaisesRegex(ValueError, "MIXED_ADJUSTMENT_STATUS"):
            walk_forward(payload)

    def test_reports_insufficient_history(self):
        result = walk_forward(candles(80), train_size=60, test_size=10)
        self.assertEqual(result["status"], "INSUFFICIENT_HISTORY")


if __name__ == "__main__":
    unittest.main()
