import unittest
from datetime import date,timedelta
from app.risk_qualification import qualify

def candles(n=60):
    start=date(2026,9,15)
    return {"candles":[{
        "trade_date":(start+timedelta(days=i)).isoformat(),
        "open":100+i*.4,"high":102+i*.4,"low":99+i*.4,
        "close":101+i*.4,"volume":1000,"adjustment_status":"RAW_UNADJUSTED"
    } for i in range(n)]}

class QualificationTests(unittest.TestCase):
    def test_valid_data_returns_observations_not_signals(self):
        result=qualify(candles(),as_of=date(2026,11,13))
        self.assertEqual(result["status"],"OBSERVATIONS_READY")
        self.assertIn("rsi_14",result["observations"])
        self.assertNotIn("recommendation",result)
        self.assertNotIn("target",result)

    def test_stale_data_blocks(self):
        result=qualify(candles(),as_of=date(2026,12,30))
        self.assertEqual(result["status"],"BLOCKED")
        self.assertIn("STALE_OR_FUTURE_DATA",result["failures"])

    def test_short_history_blocks(self):
        result=qualify(candles(10),as_of=date(2026,9,24))
        self.assertEqual(result["status"],"BLOCKED")

    def test_mixed_adjustment_blocks(self):
        data=candles()
        data["candles"][-1]["adjustment_status"]="ADJUSTED"
        result=qualify(data,as_of=date(2026,11,13))
        self.assertIn("MIXED_ADJUSTMENT_STATUS",result["failures"])

    def test_invalid_prices_block(self):
        data=candles()
        data["candles"][-1]["low"]=-1
        result=qualify(data,as_of=date(2026,11,13))
        self.assertIn("INVALID_OHLCV",result["failures"])

if __name__=="__main__":
    unittest.main()
