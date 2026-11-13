"""Synthetic fixtures only: these values are not production market records."""
import unittest
from unittest.mock import patch
from app.technical import Candle,compute,levels
from app.patterns import detect
import app.main as main

def rising(n=220):
    return [Candle(f"2026-01-{(i%28)+1:02d}",100+i,101+i,99+i,100+i,i+1000,"ADJUSTED") for i in range(n)]

class TechnicalTests(unittest.TestCase):
    def test_indicator_reference_values_and_warmup(self):
        result=compute(rising())
        self.assertIsNone(result["sma_20"][18]);self.assertEqual(result["sma_20"][19],109.5)
        self.assertEqual(round(result["ema_9"][8],6),104.0);self.assertEqual(result["rsi_14"][-1],100)
        self.assertEqual(round(result["momentum_20d"][-1],8),round(319/299-1,8));self.assertIsNotNone(result["sma_200"][-1])
        self.assertTrue(all(v is None for v in result["vwap"]),"Daily candles cannot provide true intraday VWAP")
    def test_explainable_patterns_do_not_use_future_confirmation(self):
        candles=[Candle("2026-01-01",10,10.2,8,10.1,100),Candle("2026-01-02",10,10.3,9.8,10.2,100)]
        hammer=next(x for x in detect(candles,compute(candles)) if x["pattern_type"]=="HAMMER")
        self.assertEqual(hammer["confirmation_status"],"UNCONFIRMED");self.assertEqual(hammer["supporting_candles"],["2026-01-01"])
        self.assertIn("later completed",hammer["invalidation_conditions"])
    def test_api_contract_insufficient_and_mixed_adjustment(self):
        fixture={"instrument":{"id":7,"exchange":"NSE","symbol":"TEST","security_name":"Synthetic Test"},"candles":[
          {"trade_date":"2026-01-01","open":10,"high":11,"low":9,"close":10.5,"volume":100,"adjustment_status":"RAW_UNADJUSTED","revision":1},
          {"trade_date":"2026-01-02","open":10.5,"high":12,"low":10,"close":11.5,"volume":120,"adjustment_status":"ADJUSTED","revision":1}]}
        with patch.object(main,"backend_json",return_value=fixture): body=main.technical_analysis(7)
        self.assertEqual(body["status"],"INSUFFICIENT_HISTORY");self.assertIn("MIXED_ADJUSTMENT_STATUS",body["missing_data"])
        self.assertEqual(body["patterns"][0]["instrument"]["symbol"],"TEST")
    def test_levels_are_bounded_and_deterministic(self): self.assertEqual(set(levels(rising(70))),{"support","resistance"})

if __name__=="__main__":unittest.main()
