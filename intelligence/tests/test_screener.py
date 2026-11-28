import unittest
from datetime import date, timedelta
from app.screener import screen, report_close_history
from app.technical import Candle

def candles(n=25, offset=0):
    start=date(2026,10,20)
    return {"candles":[{
        "trade_date":(start+timedelta(days=i)).isoformat(),
        "open":100+i+offset,"high":102+i+offset,"low":99+i+offset,
        "close":101+i+offset,"volume":1000,"adjustment_status":"RAW_UNADJUSTED"
    } for i in range(n)]}

class ScreenerTests(unittest.TestCase):
    def test_report_close_history_is_bounded_and_preserves_observation_dates(self):
        rows=[Candle((date(2026,9,1)+timedelta(days=i*2)).isoformat(),
                     100,200,90,100+i,1000,"ADJUSTED") for i in range(40)]
        report=report_close_history(rows)
        self.assertEqual(len(report["points"]),30)
        self.assertEqual(report["points"][0],{"date":rows[10].date,"close":110})
        self.assertEqual(report["points"][-1],{"date":rows[-1].date,"close":139})
        self.assertEqual(report["as_of"],rows[-1].date)
        self.assertEqual(report["adjustment_status"],"ADJUSTED")

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

    def test_batch_calendar_rejects_wrong_session(self):
        row={"id":1,"exchange":"NSE","symbol":"TEST"}
        result=screen([row],lambda _:candles(),as_of=date(2026,11,14),
                      batch_loaded=True,expected_session=date(2026,11,12))
        self.assertEqual(result["eligible_count"],0)
        self.assertEqual(result["skipped"]["SESSION_MISMATCH"],1)

    def test_raw_history_crossing_recorded_action_is_not_ranked(self):
        row={"id":1,"exchange":"NSE","symbol":"TEST","latest_action_date":"2026-11-02"}
        result=screen([row],lambda _:candles(),as_of=date(2026,11,14),batch_loaded=True)
        self.assertEqual(result["eligible_count"],0)
        self.assertEqual(result["skipped"]["RAW_CORPORATE_ACTION"],1)
        adjusted=candles()
        for candle in adjusted["candles"]:
            candle["adjustment_status"]="ADJUSTED"
        result=screen([row],lambda _:adjusted,as_of=date(2026,11,14),batch_loaded=True)
        # A label alone cannot reconcile a recorded crossing. No event
        # crossing remains eligible for preliminary screening as before.
        self.assertEqual(result["eligible_count"],0)
        self.assertEqual(result["skipped"]["ADJUSTED_ACTION_RECONCILIATION"],1)
        self.assertEqual(result["top_gainers"],[])
        result=screen([{**row,"latest_action_date":"2026-10-19"}],lambda _:adjusted,
                      as_of=date(2026,11,14),batch_loaded=True)
        self.assertEqual(result["eligible_count"],1)

if __name__=="__main__":
    unittest.main()
