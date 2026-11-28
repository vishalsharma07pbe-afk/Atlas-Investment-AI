import unittest
from datetime import date
from app import emerging_opportunities as e
def setup():
    return {"adjustment_status":"ADJUSTED","calendar_matched":True,"observations":253,"return_252_percent":40,
        "return_60_percent":8,"max_daily_gain_20_percent":4,"turnover_cr":15,"near_annual_high_percent":90,"above_sma200":True,
        "professional_patterns":{"contraction_checks":{"older_range_percent":20,"middle_range_percent":12,"recent_range_percent":6,"recent_to_prior_volume":.6,"pivot_confirmed":False}}}
class EmergingTest(unittest.TestCase):
    def test_price_setup_is_not_a_business_claim(self):
        r={"isin":"INE002A01018","id":1,"exchange":"NSE","symbol":"TEST","as_of":"2026-11-27"}
        f=setup();today=date(2026,11,28)
        self.assertEqual(e.assess(r,f,{},today)["state"],"PRICE_SETUP_AWAITING_BUSINESS_EVIDENCE")
        report={"isin":r["isin"],"quarterly_financials":{"latest_period":"2026-09-30","items":[
            {"metric":"revenue","year_over_year_growth_percent":12,"growth_acceleration_pp":5},
            {"metric":"net_profit","year_over_year_growth_percent":20,"growth_acceleration_pp":8}]}}
        self.assertEqual(e.assess(r,f,report,today)["state"],"EARLY_CONVERGENCE_RESEARCH")
        report["quarterly_financials"]["items"][1]["growth_acceleration_pp"]=-2
        self.assertEqual(e.assess(r,f,report,today)["state"],"BUSINESS_TREND_CAUTION")
        f["return_252_percent"]=100
        self.assertIsNone(e.assess(r,f,report,today))
