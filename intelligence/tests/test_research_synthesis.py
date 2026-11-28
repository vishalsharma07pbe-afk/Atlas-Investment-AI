import unittest
from datetime import date,datetime,timezone,timedelta
from app import research_synthesis as s

class ResearchSynthesisTest(unittest.TestCase):
    def test_quarter_sensitivities_are_explicit_and_identity_bound(self):
        now=datetime(2026,11,28,5,tzinfo=timezone.utc)
        b={"methodology":"QUARTER-PERSISTENCE-1","qualified":False,"isin":"INE002A01018",
           "capture_at":now.isoformat(),"observed_quarter":"2026-09-30","target_quarter":"2026-12-31",
           "metrics":{"revenue":{"target_prior_year_amount_cr":100,"persisted_growth_percent":20},
                      "net_profit":{"target_prior_year_amount_cr":10,"persisted_growth_percent":10}}}
        self.assertTrue(s.current_baseline(b,b["isin"],now))
        self.assertFalse(s.current_baseline(b,"INE467B01029",now))
        self.assertFalse(s.current_baseline(b,b["isin"],now+timedelta(days=2)))
        rows=s.quarter_scenarios(b)
        self.assertEqual([r["revenue_amount_cr"] for r in rows],[110,120,130])
        self.assertEqual([r["net_profit_amount_cr"] for r in rows],[10,11,12])
        self.assertEqual(s.quarter_scenarios({"metrics":{}}),[])

    def test_fund_costs_are_current_exact_and_conflict_aware(self):
        day=date(2026,11,28)
        row={"identifier":"123456","isin_growth":"INF123456789","weekly_drawdown_percent":-15}
        ter={"status":"OPERATOR_CROSSWALK_MATCH","isin_growth":row["isin_growth"],
             "ter_date":"2026-11-27","ter_percent":.7}
        d={"identifier":"123456","plan":"DIRECT","option":"GROWTH","automatic_amfi_ter_evidence":ter}
        self.assertEqual(s.fund_context(row,d,day)["ter_percent"],.7)
        self.assertNotIn("ter_percent",s.fund_context(row,{**d,"identifier":"123457"},day))
        self.assertNotIn("ter_percent",s.fund_context(row,d,day+timedelta(days=10)))
        ter["status"]="CONFLICTING_SAME_DATE_TER"
        self.assertNotIn("ter_percent",s.fund_context(row,d,day))
        self.assertEqual(s.fund_context(row,d,day)["weekly_drawdown_percent"],-15)

    def test_thesis_never_promotes_adverse_fund(self):
        row={"tier":"DRIVER_REVIEW","reasons":["Observed peer return"],"limitations":["No verified TER"]}
        thesis=s.thesis(row,True)
        self.assertFalse(thesis["qualified"])
        self.assertIn("Underlying business evidence requires review before a new SIP.",thesis["bear_case"])
        self.assertEqual(thesis["missing_evidence"],["No verified TER"])
