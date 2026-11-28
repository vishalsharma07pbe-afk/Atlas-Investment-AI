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
