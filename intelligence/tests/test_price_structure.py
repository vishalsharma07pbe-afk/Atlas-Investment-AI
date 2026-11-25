import unittest
from datetime import date,timedelta
from app.technical import Candle,compute
from app.price_structure import analyze


def fixture(adjustment="ADJUSTED"):
    start=date(2026,8,1)
    values=[100.0]*30
    values[10]=90.0
    values[20]=120.0
    return [Candle((start+timedelta(days=i)).isoformat(),v,v+1,v-1,v,100000,adjustment)
            for i,v in enumerate(values)]


class PriceStructureTests(unittest.TestCase):
    def test_confirmed_levels_and_cost_adjusted_geometry(self):
        rows=fixture()
        result=analyze(rows,compute(rows),"SWING",calendar_verified=True)
        self.assertEqual(result["support"][0]["price"],89)
        self.assertEqual(result["resistance"][0]["price"],121)
        self.assertEqual(result["resistance"][0]["confirmed_on"],rows[22].date)
        self.assertEqual(result["scenario_status"],"ILLUSTRATIVE_HISTORICAL_GEOMETRY")
        s=result["scenario"]
        self.assertAlmostEqual(s["downside_percent"],100*(100.3-89*.997)/100.3,places=3)
        self.assertAlmostEqual(s["upside_percent"],100*(121*.997-100.3)/100.3,places=3)

    def test_raw_and_unverified_histories_withhold_scenario(self):
        for rows,verified,status in [(fixture("RAW_UNADJUSTED"),True,"ADJUSTED_HISTORY_REQUIRED"),
                                      (fixture(),False,"CALENDAR_UNVERIFIED")]:
            result=analyze(rows,compute(rows),"SWING",calendar_verified=verified)
            self.assertIsNone(result["scenario"])
            self.assertEqual(result["scenario_status"],status)

    def test_unconfirmed_last_bar_does_not_become_target(self):
        rows=fixture()
        rows[20]=Candle(rows[20].date,100,101,99,100,100000,"ADJUSTED")
        rows[-2]=Candle(rows[-2].date,120,121,119,120,100000,"ADJUSTED")
        result=analyze(rows,compute(rows),"SWING",calendar_verified=True)
        self.assertEqual(result["resistance"],[])
        self.assertIsNone(result["scenario"])

    def test_large_gap_rejects_structure(self):
        rows=fixture()
        rows=rows[:5]+rows[14:]
        self.assertEqual(analyze(rows,compute(rows),"SWING",True)["status"],"UNAVAILABLE")

    def test_weekly_excludes_latest_observed_week(self):
        start=date(2026,1,5)
        dates=[start+timedelta(days=7*w+d) for w in range(21) for d in range(5)]
        rows=[Candle(d.isoformat(),100+i,101+i,99+i,100+i,100000,"ADJUSTED") for i,d in enumerate(dates)]
        result=analyze(rows,compute(rows),"SHORT_TERM",True)["weekly"]
        self.assertEqual(result["week_count"],20)
        self.assertEqual(result["last_observed_date"],rows[-6].date)
        self.assertEqual(result["trend"],"ABOVE_BOTH")


    def test_cost_and_gap_stress_and_price_ceiling(self):
        rows=fixture()
        result=analyze(rows,compute(rows),"SWING",calendar_verified=True)
        research=result["risk_sensitivity"]
        self.assertEqual(research["status"],"ILLUSTRATIVE_COST_AND_GAP_STRESS")
        self.assertEqual(research["observed_gap_count"],29)
        self.assertAlmostEqual(research["worst_adverse_open_gap_percent"],100*(1-100/120),places=3)
        self.assertEqual(research["worst_adverse_gap_date"],rows[21].date)
        self.assertAlmostEqual(research["stressed_lower_reference"],89*(100/120),places=3)
        self.assertEqual([r["cost_bps_per_side"] for r in research["scenarios"]],[15,30,60])
        a,b,d=research["scenarios"]
        self.assertAlmostEqual(b["upside_percent"],result["scenario"]["upside_percent"])
        self.assertAlmostEqual(b["downside_percent"],result["scenario"]["downside_percent"])
        self.assertGreater(b["stressed_downside_percent"],b["downside_percent"])
        self.assertGreater(a["illustrative_price_ceiling"],d["illustrative_price_ceiling"])
        self.assertAlmostEqual(b["illustrative_price_ceiling"],(121+2*89)*.997/(3*1.003),places=3)
        self.assertLess(b["stressed_reward_to_risk"],b["reward_to_risk"])
        self.assertIsNone(b["stressed_price_ceiling"])
        self.assertFalse(b["reference_meets_stressed_ratio"])

    def test_sensitivity_withheld_without_verified_adjusted_bracket(self):
        for rows,verified in [(fixture("RAW_UNADJUSTED"),True),(fixture(),False)]:
            self.assertIsNone(analyze(rows,compute(rows),"SWING",verified)["risk_sensitivity"])
        rows=fixture()
        rows[20]=Candle(rows[20].date,100,101,99,100,100000,"ADJUSTED")
        self.assertIsNone(analyze(rows,compute(rows),"SWING",True)["risk_sensitivity"])
