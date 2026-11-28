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

    def test_matched_tri_and_reported_disclosures_keep_their_basis(self):
        today=date(2026,11,28)
        r={"identifier":"123456","nav_date":"2026-11-27"}
        d={"identifier":"123456","plan":"DIRECT","option":"GROWTH",
           "secondary_disclosure":{"status":"SECONDARY_REPORTED_NOT_INDEPENDENTLY_VERIFIED","document_date":"2026-11-01","fund_managers":"Reported manager"},
           "local_export_evidence":{"disclosure":{"benchmark":"NIFTY 100 TRI"},
           "benchmark_comparison":{"status":"MATCHED_LOCAL_TRI_EXPORT","matched_anchors":157,"rolling_windows":105,
           "above_tri_percent":60,"annualized_weekly_active_volatility_percent":5,
           "windows":[{"weeks":156,"last_date":"2026-11-27","fund_cagr_percent":12,"tri_cagr_percent":10,"difference_pp":2}]}}}
        out=s.fund_context(r,d,today)
        self.assertEqual(out["benchmark_context"]["three_year_difference_pp"],2)
        self.assertEqual(out["reported_metadata"]["basis"],"SECONDARY_REPORTED")
        self.assertNotIn("reported_metadata",s.fund_context(r,d,today+timedelta(days=100)))
        self.assertNotIn("benchmark_context",s.fund_context({**r,"nav_date":"2026-11-26"},d,today))

    def test_filing_context_requires_identity_date_and_permission(self):
        from unittest.mock import patch
        now=datetime(2026,11,28,5,tzinfo=timezone.utc)
        r={"isin":"INE002A01018","independent_financial_evidence":{"isin":"INE002A01018","status":"REPORTED_CONSOLIDATED_FILING",
            "scope":"CONSOLIDATED","period":"2026-09-30","retrieved_at":now.isoformat(),"source_sha256":"a"*64,
            "comparison":{"status":"WITHIN_ILLUSTRATIVE_TOLERANCE","profit_comparison":{"status":"ONE_REPORTED_BASIS_WITHIN_TOLERANCE"}}}}
        with patch("app.nse_financial_filings.permitted",return_value=True):
            self.assertEqual(s.filing_context(r,now)["status"],"CORROBORATED_REPORTED_QUARTER")
            self.assertIsNone(s.filing_context({**r,"isin":"INE467B01029"},now))
            self.assertIsNone(s.filing_context(r,now+timedelta(hours=25)))
            r["independent_financial_evidence"]["comparison"]["profit_comparison"]["status"]="PROFIT_DIFFERENCE_REVIEW"
            self.assertEqual(s.filing_context(r,now)["status"],"CONFLICT_REVIEW")
        with patch("app.nse_financial_filings.permitted",return_value=False):self.assertIsNone(s.filing_context(r,now))
