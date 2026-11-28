import unittest
from datetime import date,timedelta
from app import multi_strategy_replay as r
from app.technical import Candle

class ReplayTests(unittest.TestCase):
    def test_entry_after_signal_and_costs(self):
        c=[Candle((date(2025,1,1)+timedelta(days=i)).isoformat(),100,111,99,110 if i==20 else 100,1_000_000,"ADJUSTED") for i in range(22)]
        v=r.metrics(c,1,21,[0],30)
        self.assertEqual(v["trades"],1)
        self.assertAlmostEqual(v["net_return_percent"],100*(1.1*(1-.003)**2-1),places=5)
        self.assertIsNone(v["profit_factor"])
        self.assertIsNone(v["cagr_percent"])
        self.assertEqual(r.positions_for({0:{"FIP"},1:{"FIP"},20:{"FIP"}},"FIP",1,21),[0])
    def test_correlation_requires_independent_folds(self):
        self.assertIsNone(r.pearson([1,2,3],[1,2,3]))
        self.assertEqual(r.pearson([1,2,3,4],[4,3,2,1]),-1)
    def test_replay_withholds_invalid_history(self):
        self.assertEqual(r.replay({"candles":[]},None,date(2026,11,28))["status"],"EVIDENCE_GAP")

    def test_prior_signal_policy_results_do_not_count(self):
        p={"isin":"INE002A01018","multi_strategy_replay":{"methodology":r.VERSION,
              "status":"DESCRIPTIVE_REPLAY_ONLY","as_of":"2026-11-27","lanes":{}}}
        self.assertEqual(r.summarize([p],date(2026,11,28))["companies"],0)
        p["multi_strategy_replay"]["signal_policy"]=r.SIGNAL_POLICY
        self.assertEqual(r.summarize([p],date(2026,11,28))["companies"],1)

    def test_turtle_channel_exit_is_next_open_and_cash_capped(self):
        c=[Candle((date(2025,1,1)+timedelta(days=i)).isoformat(),100,101,99,100,1_000_000,"ADJUSTED") for i in range(260)]
        c[253]=Candle(c[253].date,100,101,94,95,1_000_000,"ADJUSTED")
        c[254]=Candle(c[254].date,90,91,89,90,1_000_000,"ADJUSTED")
        result=r.turtle_channel_replay(c,{252:{"TURTLE_LONG_BREAKOUT"}},253,259)
        self.assertEqual(result["completed_trades"],1)
        self.assertFalse(result["open_position"])
        self.assertLess(result["net_marked_return_percent"],-2.5)
        self.assertFalse(result["qualified"])
