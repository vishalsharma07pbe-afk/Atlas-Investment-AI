import unittest
from datetime import date,timedelta
from unittest.mock import patch
from app.strategy_validation import replay, _metrics

TODAY=date(2026,11,24)

def history(count=500):
    start=TODAY-timedelta(days=count)
    rows=[]
    for i in range(count):
        p=100+i*.1
        rows.append({"trade_date":(start+timedelta(days=i)).isoformat(),"open":p,"high":p+1,"low":p-1,
                     "close":p+.2,"volume":200000,"adjustment_status":"ADJUSTED",
                     "quality_status":"PROVIDER_VALIDATED","source_code":"TEST"})
    return {"candles":rows}

class StrategyValidationTests(unittest.TestCase):
    def test_chronological_nonoverlapping_holdout_and_costs(self):
        seen=[]
        def signal(candles,indicators,base):
            self.assertTrue(all(len(v)==len(candles) for v in indicators.values()))
            seen.append(len(candles))
            return {h:("TECHNICAL_WATCH",{}) for h in ("SWING","SHORT_TERM","LONG_TERM")}
        with patch("app.strategy_validation.evaluate",side_effect=signal):
            result=replay(history(),TODAY)
        self.assertEqual(result["status"],"HISTORICAL_REPLAY_ONLY")
        self.assertGreaterEqual(min(seen),301)
        swing=result["horizons"]["SWING"]
        self.assertEqual(swing["trades"],19)
        self.assertTrue(swing["small_sample"])
        self.assertGreater(swing["cost_scenarios"][0]["net_return_percent"],swing["cost_scenarios"][-1]["net_return_percent"])
        self.assertEqual(result["horizons"]["LONG_TERM"]["trades"],1)

    def test_unadjusted_mixed_source_stale_or_gapped_history_fails_closed(self):
        for field,value in (("adjustment_status","RAW_UNADJUSTED"),("source_code","OTHER"),("quality_status","UNKNOWN")):
            data=history()
            data["candles"][0][field]=value
            self.assertEqual(replay(data,TODAY)["status"],"EVIDENCE_GAP")
        self.assertEqual(replay(history(),TODAY+timedelta(days=9))["status"],"EVIDENCE_GAP")
        data=history()
        del data["candles"][50:60]
        self.assertEqual(replay(data,TODAY)["status"],"EVIDENCE_GAP")

    def test_insufficient_history_and_no_signal_are_not_performance(self):
        self.assertEqual(replay(history(100),TODAY)["status"],"INSUFFICIENT_HISTORY")
        with patch("app.strategy_validation.evaluate",return_value={h:("RULES_NOT_MET",None) for h in ("SWING","SHORT_TERM","LONG_TERM")}):
            result=replay(history(),TODAY)
        self.assertEqual(result["horizons"]["SWING"]["status"],"NO_SIGNALS")
        self.assertEqual(result["horizons"]["SWING"]["cost_scenarios"],[])

    def test_known_round_trip_cost_and_drawdown(self):
        result=_metrics([(100,110,[90,110])],30)
        self.assertAlmostEqual(result["net_return_percent"],(1.1*.997*.997-1)*100,places=3)
        self.assertAlmostEqual(result["max_drawdown_percent"],-10.27,places=2)
        self.assertEqual(result["wins"],1)
        self.assertEqual(result["losses"],0)
