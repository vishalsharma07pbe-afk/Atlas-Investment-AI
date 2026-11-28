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
        self.assertNotIn("PEAD",m.LANES)
        self.assertNotIn("PIOTROSKI_FULL",m.LANES)
    def test_overextension_rejected_for_price_leads(self):
        f={"methodology":m.VERSION,"turnover_cr":10,"return_252_percent":120,"above_sma200":True,"sma50_above_sma200":True,"return_60_percent":12,"near_annual_high_percent":98}
        self.assertEqual(m.price_lanes(f),[])
