import unittest
from datetime import date,timedelta
from app.backtesting import backtest

def data(n=80):
    start=date(2026,1,1)
    return {"candles":[{
        "trade_date":(start+timedelta(days=i)).isoformat(),
        "open":100+i*0.4,"high":102+i*0.4,"low":99+i*0.4,
        "close":101+i*0.4,"volume":1000,"adjustment_status":"RAW_UNADJUSTED"
    } for i in range(n)]}

class BacktestTests(unittest.TestCase):
    def test_no_crossovers_remains_in_cash(self):
        result=backtest(data(),fast=5,slow=20)
        self.assertEqual(result["status"],"HISTORICAL_SIMULATION_ONLY")
        self.assertEqual(result["strategy_total_return_percent"],0)
        self.assertEqual(result["closed_trade_count"],0)
        self.assertFalse(result["open_position_at_end"])

    def test_insufficient_history(self):
        result=backtest(data(10),fast=5,slow=20)
        self.assertEqual(result["status"],"INSUFFICIENT_HISTORY")

    def test_rejects_mixed_adjustments(self):
        payload=data()
        payload["candles"][-1]["adjustment_status"]="ADJUSTED"
        with self.assertRaises(ValueError):
            backtest(payload)

    def test_rejects_nonmonotonic_dates(self):
        payload=data()
        payload["candles"][2]["trade_date"]=payload["candles"][1]["trade_date"]
        with self.assertRaises(ValueError):
            backtest(payload)

    def test_crossovers_fill_next_open_with_costs(self):
        payload=data(100)
        # Oscillating long waves generate completed-close crossovers.
        for i,x in enumerate(payload["candles"]):
            value=100+20*((i//15)%2)
            x.update(open=value,close=value,high=value+1,low=value-1)
        result=backtest(payload,fast=3,slow=10,fee_bps=10,slippage_bps=5)
        self.assertGreater(result["closed_trade_count"],0)
        self.assertLessEqual(result["max_drawdown_percent"],0)
        self.assertTrue(all(t["entry_date"]<t["exit_date"] for t in result["trades"]))

if __name__=="__main__":
    unittest.main()
