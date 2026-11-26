import unittest
from datetime import date,timedelta
from app.research_alerts import AlertRule,evaluate_alerts

def candles(n=60):
    start=date(2026,9,15)
    return {"candles":[{
        "trade_date":(start+timedelta(days=i)).isoformat(),
        "open":100+i*.4,"high":102+i*.4,"low":99+i*.4,
        "close":101+i*.4,"volume":1000,"adjustment_status":"RAW_UNADJUSTED"
    } for i in range(n)]}

class AlertTests(unittest.TestCase):
    def test_triggered_and_untriggered(self):
        rules=[AlertRule(metric="CLOSE_ABOVE",threshold=120),
               AlertRule(metric="CLOSE_BELOW",threshold=90)]
        result=evaluate_alerts(candles(),rules,as_of=date(2026,11,13))
        self.assertEqual(result["status"],"EVALUATED")
        self.assertEqual(result["triggered_count"],1)
        self.assertTrue(result["alerts"][0]["triggered"])
        self.assertFalse(result["alerts"][1]["triggered"])

    def test_stale_data_blocks_all_alerts(self):
        result=evaluate_alerts(candles(),[AlertRule(metric="CLOSE_ABOVE",threshold=1)],
                               as_of=date(2026,12,30))
        self.assertEqual(result["status"],"BLOCKED")
        self.assertEqual(result["alerts"],[])

    def test_insufficient_history_blocks(self):
        result=evaluate_alerts(candles(5),[AlertRule(metric="CLOSE_ABOVE",threshold=1)],
                               as_of=date(2026,9,19))
        self.assertEqual(result["status"],"BLOCKED")

    def test_invalid_rsi_threshold_rejected(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            AlertRule(metric="RSI_ABOVE",threshold=101)

if __name__=="__main__":
    unittest.main()
