import unittest
from datetime import date,timedelta
from app import multi_strategy as m
from app.technical import Candle

class MultiStrategyTest(unittest.TestCase):
    def test_trend_and_price_basis(self):
        start=date(2025,1,1)
        c=[Candle((start+timedelta(days=i)).isoformat(),100+i*.2,101+i*.2,99+i*.2,100+i*.2,1_000_000,"ADJUSTED") for i in range(253)]
        f=m.price_features(c,[v.date for v in c])
        self.assertTrue(f["calendar_matched"])
        self.assertIn("TREND_FOLLOWING",m.price_lanes(f))
        self.assertIn("HIGH_52_WEEK",m.price_lanes(f))
        self.assertFalse(m.price_features(c)["calendar_matched"])
    def test_no_fabricated_pead_or_full_fscore(self):
        self.assertEqual(m.financial_lanes({},date(2026,11,28)),([],{}))
        from app.professional_strategies import catalog
        self.assertEqual(catalog({})["PEAD"]["status"],"AWAITING_VERIFIED_EXPECTATIONS_FEED")
        self.assertEqual(catalog({})["PEAD"]["matches"],0)
        self.assertFalse(catalog({})["PIOTROSKI_F_SCORE"]["qualified"])
    def test_overextension_rejected_for_price_leads(self):
        f={"methodology":m.VERSION,"turnover_cr":10,"return_252_percent":120,"above_sma200":True,"sma50_above_sma200":True,"return_60_percent":12,"near_annual_high_percent":98}
        self.assertEqual(m.price_lanes(f),[])

    def test_pump_guard_preserves_no_match_on_known_jump(self):
        f={"methodology":m.VERSION,"turnover_cr":10,"return_252_percent":50,
           "above_sma200":True,"sma50_above_sma200":True,"return_60_percent":20,
           "near_annual_high_percent":98,"max_daily_gain_20_percent":10}
        self.assertEqual(m.price_lanes(f),[])
        self.assertFalse(m.pump_or_extended({**f,"max_daily_gain_20_percent":9}))
        self.assertFalse(m.pump_or_extended({}))

    def test_sample_momentum_requires_both_exact_date_windows(self):
        from unittest.mock import patch
        candidates=[{"isin":str(i),"multi_strategy_price":{
            "adjustment_status":"ADJUSTED","calendar_matched":True,"observations":253,
            "full_dates_digest":"same","volatility_126_percent":20,
            "momentum_6_ex_recent":i,"momentum_12_ex_recent":i}} for i in range(20)]
        with patch.object(m,"exact_isin",return_value=True):
            ranks=m.sample_momentum_ranks(candidates)
            self.assertEqual(ranks["19"]["percentile"],97.5)
            self.assertEqual(ranks["0"]["percentile"],2.5)
            self.assertEqual(ranks["19"]["sample_size"],20)
            candidates[0]["multi_strategy_price"]["momentum_12_ex_recent"]=None
            self.assertEqual(m.sample_momentum_ranks(candidates),{})
