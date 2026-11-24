import unittest
from datetime import date,timedelta
from app.screener import screen
from app.horizon_research import evaluate,summarize
from app.technical import Candle

def fixture(n):
    start=date(2025,1,1)
    return [Candle((start+timedelta(days=i)).isoformat(),100,102,99,101,200000) for i in range(n)]

def indicators():
    values={"rsi_14":60,"atr_14":2,"relative_volume_20":1.4,
            "sma_20":99,"sma_50":98,"sma_100":97,"sma_200":96,"momentum_20d":.05}
    return {k:[v] for k,v in values.items()}

class HorizonResearchTests(unittest.TestCase):
    def test_distinct_history_gates_and_no_intraday_from_daily(self):
        rows=fixture(60)
        result=evaluate(rows,indicators(),{"id":1,"symbol":"TEST","exchange":"NSE"})
        self.assertEqual(result["SWING"][0],"TECHNICAL_WATCH")
        self.assertEqual(result["SHORT_TERM"][0],"INSUFFICIENT_HISTORY")
        self.assertEqual(result["LONG_TERM"][0],"INSUFFICIENT_HISTORY")
        summary=summarize([result])
        self.assertEqual(summary["INTRADAY"]["candidates"],[])
        self.assertEqual(summary["INTRADAY"]["evaluated_count"],0)
        self.assertEqual(summary["SWING"]["matched_count"],1)
        self.assertIn("STRATEGY_BACKTEST_NOT_VERIFIED",summary["SWING"]["blockers"])

    def test_low_historical_turnover_excluded(self):
        rows=[Candle(c.date,c.open,c.high,c.low,c.close,1) for c in fixture(60)]
        result=evaluate(rows,indicators(),{"id":1,"symbol":"TEST","exchange":"NSE"})
        self.assertEqual(result["SWING"][0],"LOW_HISTORICAL_TURNOVER")

    def test_stale_rows_never_enter_horizons(self):
        raw={"candles":[{"trade_date":c.date,"open":c.open,"high":c.high,"low":c.low,
                         "close":c.close,"volume":c.volume,"adjustment_status":c.adjustment_status} for c in fixture(60)]}
        result=screen([{"id":1,"symbol":"TEST","exchange":"NSE"}],lambda _:raw,
                      as_of=date(2026,1,1),include_horizons=True)
        self.assertEqual(result["skipped"]["STALE"],1)
        self.assertEqual(result["horizons"]["SWING"]["evaluated_count"],0)

    def test_ranked_results_are_bounded_and_not_recommendations(self):
        evaluations=[]
        for i in range(8):
            evaluations.append(evaluate(fixture(60),indicators(),{"id":i,"symbol":f"TEST{i}","exchange":"NSE"}))
        result=summarize(evaluations)["SWING"]
        self.assertEqual(result["matched_count"],8)
        self.assertEqual(len(result["candidates"]),5)
        self.assertEqual(result["status"],"TECHNICAL_WATCH_ONLY")
