import unittest
from datetime import date,timedelta
from unittest.mock import patch
from app.strategy_validation import replay, _metrics, attach_market_benchmark

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

    def test_actual_long_term_rule_is_reused(self):
        result=replay(history(),TODAY)
        self.assertEqual(result['horizons']['LONG_TERM']['status'],'REPLAY_OBSERVED')
        self.assertEqual(result['horizons']['LONG_TERM']['trades'],1)

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

    def test_cost_adjusted_same_stock_reference_uses_identical_holdout(self):
        rows=history()["candles"]
        with patch("app.strategy_validation.evaluate",return_value={h:("TECHNICAL_WATCH",{}) for h in ("SWING","SHORT_TERM","LONG_TERM")}):
            result=replay({"candles":rows},TODAY)
        for horizon in result["horizons"].values():
            for cost in horizon["cost_scenarios"]:
                reference=(rows[-1]["close"]/rows[301]["open"])*(1-cost["cost_bps_per_side"]/10000)**2
                self.assertAlmostEqual(cost["net_same_stock_buy_hold_percent"],(reference-1)*100,places=3)
                self.assertAlmostEqual(cost["net_difference_vs_same_stock_pp"],
                    cost["net_return_percent"]-cost["net_same_stock_buy_hold_percent"],places=3)

    def test_nifty_price_index_exact_observed_interval_and_fail_closed(self):
        data=history()
        with patch("app.strategy_validation.evaluate",return_value={h:("TECHNICAL_WATCH",{}) for h in ("SWING","SHORT_TERM","LONG_TERM")}):
            result=replay(data,TODAY)
        rows=[{"trade_date":row["trade_date"],"open":200,"close":220,"revision":1,"source_code":"UPSTOX"}
              for row in data["candles"][-250:]]
        benchmark={"benchmark_key":"NSE_INDEX|Nifty 50","kind":"PRICE_INDEX","candles":rows}
        attach_market_benchmark(result,data,benchmark,TODAY)
        swing=result["horizons"]["SWING"]
        self.assertEqual(swing["market_benchmark_status"],"MATCHED_PRICE_INDEX")
        self.assertEqual(swing["market_benchmark_start"],data["candles"][301]["trade_date"])
        self.assertEqual(swing["market_benchmark_observations"],199)
        cost=swing["cost_scenarios"][0]
        self.assertEqual(cost["gross_nifty50_price_index_percent"],10)
        self.assertAlmostEqual(cost["net_difference_vs_nifty50_pp"],cost["net_return_percent"]-10,places=4)
        for invalid in (None,{**benchmark,"benchmark_key":"OTHER"},
                        {**benchmark,"candles":rows[:-1]},
                        {**benchmark,"candles":rows[:100]+rows[101:]},
                        {**benchmark,"candles":rows+[rows[-1]]},
                        {**benchmark,"candles":[{**row,"source_code":"OTHER"} for row in rows]}):
            attach_market_benchmark(result,data,invalid,TODAY)
            self.assertEqual(swing["market_benchmark_status"],"UNAVAILABLE")
            self.assertNotIn("gross_nifty50_price_index_percent",cost)
            self.assertNotIn("net_difference_vs_nifty50_pp",cost)

    def test_signal_regimes_use_only_matched_history_before_entry(self):
        data=history()
        positions={}
        with patch("app.strategy_validation.evaluate",return_value={h:("TECHNICAL_WATCH",{}) for h in ("SWING","SHORT_TERM","LONG_TERM")}):
            result=replay(data,TODAY,positions=positions)
        rows=[{"trade_date":row["trade_date"],"open":100,"close":100+i*.2,"revision":1,"source_code":"UPSTOX"}
              for i,row in enumerate(data["candles"][-300:])]
        benchmark={"benchmark_key":"NSE_INDEX|Nifty 50","kind":"PRICE_INDEX","candles":rows}
        attach_market_benchmark(result,data,benchmark,TODAY,positions=positions)
        swing=result["horizons"]["SWING"]
        regime=swing["market_regime_research"]
        self.assertEqual(regime["status"],"MATCHED")
        self.assertEqual(regime["classified_trades"],19)
        rising=regime["groups"][0]
        self.assertEqual(rising["regime"],"RISING")
        self.assertEqual(rising["trades"],19)
        self.assertEqual(rising["cost_scenarios"][1]["mean_trade_return_percent"],
                         swing["cost_scenarios"][1]["mean_trade_return_percent"])
        # Future index closes cannot change the first signal's classification.
        from app.strategy_validation import _market_regimes, _history
        equity=_history(data,TODAY)
        first=positions["SWING"][:1]
        signal=first[0][0]
        index={row["trade_date"]:(row["open"],row["close"]) for row in rows}
        changed={d:(o,c if d<=signal else 1) for d,(o,c) in index.items()}
        self.assertEqual(_market_regimes(equity,index,first),_market_regimes(equity,changed,first))
        for end,expected in ((90,"FALLING"),(100,"SIDEWAYS"),(110,"RISING")):
            exact={c.date:(100,100) for c in equity[240:301]}
            exact[signal]=(100,end)
            self.assertEqual(next(g["regime"] for g in _market_regimes(equity,exact,first)["groups"] if g["trades"]),expected)
        # Missing pre-signal observation withholds that cohort, not the replay.
        gap={**benchmark,"candles":rows[:50]+rows[51:]}
        attach_market_benchmark(result,data,gap,TODAY,positions=positions)
        self.assertEqual(swing["market_regime_research"]["status"],"PARTIAL")
        self.assertEqual(swing["market_benchmark_status"],"MATCHED_PRICE_INDEX")
        self.assertGreater(swing["market_regime_research"]["groups"][-1]["trades"],0)
        attach_market_benchmark(result,data,None,TODAY,positions=positions)
        self.assertEqual(swing["market_regime_research"]["status"],"UNAVAILABLE")
        self.assertEqual(swing["market_regime_research"]["groups"][-1]["trades"],19)
        self.assertEqual(swing["market_regime_research"]["groups"][-1]["cost_scenarios"],[])
        self.assertEqual(swing["trades"],19)

    def test_repeated_fixed_rule_windows_preserve_main_replay_and_bound_exposure(self):
        data=history()
        with patch("app.strategy_validation.evaluate",return_value={h:("TECHNICAL_WATCH",{}) for h in ("SWING","SHORT_TERM","LONG_TERM")}):
            result=replay(data,TODAY)
        swing=result["horizons"]["SWING"]
        self.assertEqual(swing["trades"],19)
        validation=swing["chronological_validation"]
        self.assertEqual(validation["status"],"REPEATED_WINDOWS_OBSERVED")
        self.assertEqual(validation["eligible_folds"],3)
        self.assertEqual(validation["observed_folds"],3)
        rows=data["candles"]
        dates=[r["trade_date"] for r in rows]
        ends=[366,432,499]
        for i,fold in enumerate(validation["folds"]):
            self.assertEqual(fold["test_end"],dates[ends[i]])
            self.assertEqual(fold["exposure_start"],dates[301 if i==0 else ends[i-1]+1])
            self.assertEqual(fold["trades"],6)
            self.assertLessEqual(fold["trades"]*10,dates.index(fold["test_end"])-dates.index(fold["test_start"]))
            expected=(rows[ends[i]]["close"]/rows[dates.index(fold["exposure_start"])]["open"])*.997**2
            self.assertAlmostEqual(fold["cost_scenarios"][1]["net_same_stock_buy_hold_percent"],(expected-1)*100,places=3)
        self.assertEqual(result["horizons"]["SHORT_TERM"]["chronological_validation"]["eligible_folds"],3)
        long=result["horizons"]["LONG_TERM"]["chronological_validation"]
        self.assertEqual(long["status"],"INSUFFICIENT_REPEATED_WINDOWS")
        self.assertEqual(long["folds"],[])
        self.assertEqual(result["horizons"]["LONG_TERM"]["trades"],1)

    def test_fold_no_signal_and_benchmark_gaps_are_explicit(self):
        data=history()
        def signal(candles,indicators,base):
            self.assertTrue(all(len(v)==len(candles) for v in indicators.values()))
            state="TECHNICAL_WATCH" if len(candles)<367 else "RULES_NOT_MET"
            return {h:(state,{}) for h in ("SWING","SHORT_TERM","LONG_TERM")}
        with patch("app.strategy_validation.evaluate",side_effect=signal):
            result=replay(data,TODAY)
        validation=result["horizons"]["SWING"]["chronological_validation"]
        self.assertEqual(validation["status"],"INSUFFICIENT_OBSERVED_FOLDS")
        self.assertEqual(validation["no_signal_folds"],2)
        self.assertTrue(all(not f["cost_scenarios"] for f in validation["folds"][1:]))
        self.assertEqual(sum(validation["cost_summaries"][0][k] for k in ("positive_folds","negative_folds","flat_folds")),1)
        rows=[{"trade_date":r["trade_date"],"open":100,"close":110,"revision":1,"source_code":"UPSTOX"}
              for r in data["candles"][-250:]]
        benchmark={"benchmark_key":"NSE_INDEX|Nifty 50","kind":"PRICE_INDEX","candles":rows}
        attach_market_benchmark(result,data,benchmark,TODAY)
        fold=validation["folds"][0]
        self.assertEqual(fold["market_benchmark_status"],"MATCHED_PRICE_INDEX")
        self.assertEqual(fold["cost_scenarios"][0]["gross_nifty50_price_index_percent"],10)
        attach_market_benchmark(result,data,{**benchmark,"candles":rows[:70]+rows[71:]},TODAY)
        self.assertEqual(fold["market_benchmark_status"],"UNAVAILABLE")
        self.assertNotIn("gross_nifty50_price_index_percent",fold["cost_scenarios"][0])
