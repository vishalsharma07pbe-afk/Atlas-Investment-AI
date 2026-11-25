import unittest
from datetime import date,timedelta
from dataclasses import replace
from app.technical import Candle
from app.price_volume_pressure import analyze
from app.screener import screen

def fixture():
    start=date(2026,10,1)
    rows=[Candle((start+timedelta(days=i)).isoformat(),100,102,98,100,1000) for i in range(21)]
    rows[-1]=replace(rows[-1],open=101,high=104,low=94,close=95,volume=3000)
    return rows

class PressureTests(unittest.TestCase):
    def test_causal_volume_baseline_and_rejection(self):
        rows=fixture()
        p=analyze(rows,calendar_verified=True)
        self.assertEqual(p["relative_volume"],3)
        self.assertEqual(p["change_percent"],-5)
        self.assertEqual(p["prior_range_high"],102)
        self.assertEqual(p["findings"],["HIGH_VOLUME_DECLINE_REVIEW","HIGH_VOLUME_UPSIDE_REJECTION_REVIEW"])
        self.assertEqual(analyze(rows)["status"],"UNAVAILABLE")
        self.assertEqual(analyze(rows[:-1]+[replace(rows[-1],volume=1000)],calendar_verified=True)["findings"],[])
        self.assertEqual(analyze([replace(rows[0],volume=0)]+rows[1:],calendar_verified=True)["status"],"UNAVAILABLE")
    def test_recovery_observation_and_sample_independent_of_bullish_watch(self):
        rows=fixture()
        recovery=rows[:-1]+[replace(rows[-1],open=99,high=106,low=96,close=105)]
        self.assertIn("HIGH_VOLUME_DOWNSIDE_REJECTION_OBSERVATION",analyze(recovery,calendar_verified=True)["findings"])
        raw=[{"trade_date":c.date,"open":c.open,"high":c.high,"low":c.low,"close":c.close,"volume":c.volume,"adjustment_status":c.adjustment_status} for c in rows]
        result=screen([{"id":1,"symbol":"TEST","exchange":"NSE","isin":"INE002A01018"}],lambda _:{"candles":raw},
            as_of=date(2026,10,22),batch_loaded=True,expected_session=date(2026,10,21),include_horizons=True)
        self.assertEqual(result["price_volume_review"]["flagged_count"],1)
        self.assertEqual(result["price_volume_review"]["downside_items"][0]["symbol"],"TEST")
        self.assertEqual(result["horizons"]["SWING"]["candidates"],[])
