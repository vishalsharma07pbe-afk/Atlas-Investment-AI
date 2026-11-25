import unittest
from datetime import datetime,timezone
from unittest.mock import patch
from app import fund_underlying_research as research,autonomous_research as coordinator

NOW=datetime(2026,11,25,5,tzinfo=timezone.utc)
A="INE002A01018"
B="INE009A01021"
C="INE242A01010"

def report(isin,period="2026",previous="2025",profit=120,scope="consolidated"):
    return {"isin":isin,"available_sections":3,"sections":{
      "profile":{"status":"AVAILABLE","data":{"sector":"Example sector"}},
      "income_statement":{"status":"AVAILABLE","data":{"statement_type":scope,"time_period":"yearly","units":"crore",
        "rows":[{"name":"net profit","history":[{"period":"Mar "+previous,"value":100},{"period":"Mar "+period,"value":profit}]}]}},
      "ratios":{"status":"AVAILABLE","data":[{"name":"P/E","company_value":20,"sector_value":10,"unit":"RATIO","sector_unit":"RATIO"}]}}}

class FundUnderlyingResearchTests(unittest.TestCase):
    def test_weighted_directions_and_periods_are_not_mixed(self):
        holdings=[{"isin":A,"weight_percent":40},{"isin":B,"weight_percent":25},{"isin":C,"weight_percent":10}]
        result=research.summarize(holdings,NOW,{A:report(A),B:report(B,profit=-20),C:report(C,"2025","2024")})
        self.assertEqual(result["cached_report_weight_percent"],75)
        # Mar 2025 is more than 18 months old in November 2026.
        self.assertEqual(result["annual_statement_weight_percent"],65)
        self.assertEqual(result["deterioration_review_weight_percent"],25)
        self.assertEqual(result["annual_trends"][0]["coverage"],65)
        self.assertEqual(result["annual_trends"][0]["increased"],40)
        self.assertEqual(result["annual_trends"][0]["negative_latest"],25)
        self.assertEqual(result["sector_classified_weight_percent"],75)
        self.assertEqual(result["relative_valuation"][0]["above"],75)
        self.assertEqual(result["relative_valuation"][0]["period_status"],"UNVERIFIED")
        self.assertIsNone(result["forward_earnings_coverage_percent"])
        self.assertIsNone(result["valuation_attractiveness"])

    def test_wrong_identity_and_nonconsolidated_are_excluded(self):
        result=research.summarize([{"isin":A,"weight_percent":40},{"isin":B,"weight_percent":30}],NOW,
                                  {A:report(B),B:report(B,scope="standalone")})
        self.assertEqual(result["annual_trends"],[])
        self.assertEqual(result["cached_report_weight_percent"],30)
        self.assertEqual(research.summarize([{"isin":A,"weight_percent":30}]*2,NOW,{})["status"],"INVALID_HOLDING_IDENTITIES")

    def test_exact_sector_evidence_requires_fresh_matching_upstox_profile(self):
        from datetime import timedelta
        good=report(A)
        good["retrieved_at"]=NOW.isoformat()
        good["sections"]["profile"]["source"]={"provider":"UPSTOX"}
        stale=report(B)
        stale["retrieved_at"]=(NOW-timedelta(hours=25)).isoformat()
        stale["sections"]["profile"]["source"]={"provider":"UPSTOX"}
        result=research.exact_sector_evidence([{"isin":A},{"isin":B},{"isin":C}],NOW,{A:good,B:stale,C:good})
        self.assertEqual(result,{A:{"sector":"Example sector","retrieved_at":NOW.isoformat(),"provider":"UPSTOX"}})

    def test_coordinator_requires_both_permissions_and_reuses_company_cache(self):
        with patch.object(coordinator.fund_portfolios,"permitted",return_value=False),patch.object(coordinator.automatic_company_evidence,"refresh") as refresh:
            self.assertEqual(coordinator._execute_job("FUND_COMPANY_EVIDENCE"),"DISABLED_OR_NOT_AUTHORIZED")
            refresh.assert_not_called()
        with patch.object(coordinator.fund_portfolios,"permitted",return_value=True),patch.object(coordinator.automatic_company_evidence,"permitted",return_value=True),patch.object(coordinator.fund_portfolios,"research_identities",return_value=[A,B]),patch.object(coordinator.automatic_company_evidence,"refresh") as refresh:
            self.assertEqual(coordinator._execute_job("FUND_COMPANY_EVIDENCE"),"PASS_COMPLETED")
            refresh.assert_called_once_with({"enabled":True,"sections":[]},coordinator._connect,explicit_isins=[A,B])
