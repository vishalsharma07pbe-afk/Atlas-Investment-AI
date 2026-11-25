import unittest
from datetime import date,timedelta
from app import regime_features as features, strategy_validation as validation, market_regime
from app.technical import Candle

def history():
    dates=[(date(2026,1,1)+timedelta(days=i)).isoformat() for i in range(80)]
    equity=[Candle(d,100,101,99,100,1000,"ADJUSTED") for d in dates]
    index={d:(100,100+i) for i,d in enumerate(dates)}
    return dates,equity,index

class JointRegimeTests(unittest.TestCase):
    def test_causal_groups_and_costs(self):
        dates,equity,index=history()
        positions=[(dates[60],(100,110,[95,110])),(dates[70],(100,90,[90]))]
        report=validation._joint_regimes(equity,index,positions)
        group=next(g for g in report["groups"] if g["trades"])
        self.assertEqual(group["trend"],"RISING")
        self.assertEqual(group["volatility_regime"],"BELOW_HIGH_THRESHOLD")
        self.assertEqual(group["trades"],2)
        self.assertEqual(group["cost_scenarios"][1]["wins"],1)
        self.assertLess(group["cost_scenarios"][1]["worst_position_drawdown_percent"],-10)
        first=positions[:1]
        revised={d:(o,c if d<=dates[60] else 1) for d,(o,c) in index.items()}
        self.assertEqual(validation._joint_regimes(equity,index,first)["groups"],
                         validation._joint_regimes(equity,revised,first)["groups"])
        del index[dates[20]]
        result=validation._joint_regimes(equity,index,positions)
        self.assertEqual(result["unknown_trades"],2)
        self.assertEqual(sum(g["trades"] for g in result["groups"]),0)
    def test_high_volatility_and_current_fingerprint(self):
        dates,equity,index=history()
        closes=[100 if i%2==0 else 120 for i in range(61)]
        report=features.describe(dates[:61],closes)
        self.assertEqual(report["volatility_regime"],"HIGH_HISTORICAL_VOLATILITY")
        self.assertNotEqual(report["benchmark_fingerprint"],features.describe(dates[:61],[100]*61)["benchmark_fingerprint"])
        joint=validation._joint_regimes(equity,index,[(dates[60],(100,110,[95,110]))])
        latest=joint["latest_benchmark_context"]
        current={**latest,"status":"OBSERVED_BENCHMARK_REGIME"}
        item={"exchange":"NSE","isin":"INE002A01018","as_of":dates[-1],"matched_strategy_replay":{
            "status":"REPLAY_OBSERVED","as_of":dates[-1],"joint_regime_research":joint}}
        snap={"enabled":True,"sections":[{"section":"NSE","status":"READY","result":{"horizons":{"SWING":{"candidates":[item]}}}}]}
        market_regime._attach_strategy_context(snap,current)
        self.assertEqual(item["current_regime_replay"]["status"],"SMALL_HISTORICAL_SAMPLE")
        del item["current_regime_replay"]
        current["benchmark_fingerprint"]="wrong"
        market_regime._attach_strategy_context(snap,current)
        self.assertNotIn("current_regime_replay",item)
