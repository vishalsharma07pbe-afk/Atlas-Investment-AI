import unittest
from datetime import date, timedelta
from app.screener import screen

def candles(n=25, offset=0):
    start=date(2026,10,20)
    return {"candles":[{
        "trade_date":(start+timedelta(days=i)).isoformat(),
        "open":100+i+offset,"high":102+i+offset,"low":99+i+offset,
        "close":101+i+offset,"volume":1000,"adjustment_status":"RAW_UNADJUSTED"
    } for i in range(n)]}

class ScreenerTests(unittest.TestCase):
    def test_fresh_daily_data_returns_observations(self):
        instruments=[{"id":1,"exchange":"NSE","symbol":"TEST"}]
        result=screen(instruments,lambda _:candles(),as_of=date(2026,11,13))
        self.assertEqual(result["eligible_count"],1)
        self.assertEqual(result["top_gainers"][0]["symbol"],"TEST")
        self.assertEqual(result["top_gainers"][0]["as_of"],"2026-11-13")

    def test_stale_and_short_history_are_excluded(self):
        instruments=[{"id":1,"exchange":"NSE","symbol":"OLD"},{"id":2,"exchange":"BSE","symbol":"SHORT"}]
        result=screen(instruments,lambda id:candles(25) if id==1 else candles(3),as_of=date(2026,12,15))
        self.assertEqual(result["eligible_count"],0)
        self.assertEqual(result["skipped"]["STALE"],1)
        self.assertEqual(result["skipped"]["NO_HISTORY"],1)

    def test_mixed_adjustment_is_excluded(self):
        data=candles()
        data["candles"][-1]["adjustment_status"]="ADJUSTED"
        result=screen([{"id":1,"exchange":"NSE","symbol":"TEST"}],lambda _:data,as_of=date(2026,11,13))
        self.assertEqual(result["skipped"]["MIXED_ADJUSTMENT"],1)

    def test_universe_is_bounded(self):
        instruments=[{"id":i,"exchange":"NSE","symbol":f"T{i}"} for i in range(30)]
        calls=[]
        def load(id):
            calls.append(id)
            return candles()
        result=screen(instruments,load,as_of=date(2026,11,13))
        self.assertEqual(len(calls),20)
        self.assertEqual(result["universe_size"],20)
        self.assertEqual(len(result["top_gainers"]),5)

    def test_background_scan_can_use_larger_bounded_sample(self):
        instruments=[{"id":i,"exchange":"NSE","symbol":f"T{i}"} for i in range(80)]
        result=screen(instruments,lambda _:candles(),as_of=date(2026,11,13),universe_limit=60)
        self.assertEqual(result["universe_size"],60)
        self.assertEqual(result["eligible_count"],60)
        self.assertEqual(len(result["top_gainers"]),5)

if __name__=="__main__":
    unittest.main()
