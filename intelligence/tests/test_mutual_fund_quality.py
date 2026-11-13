import unittest
from datetime import date
from app.mutual_fund_reconciliation import FundReconciliationRequest,reconcile_funds

class QualityTests(unittest.TestCase):
    def test_mixed_dates_sources_and_unused_code(self):
        request=FundReconciliationRequest(
            positions=[
                {"holding_id":1,"scheme_code":"123","units":"10","invested":"100"},
                {"holding_id":2,"scheme_code":"456","units":"20","invested":"200","recorded_value":"300"}],
            navs=[
                {"scheme_code":"123","nav":"11","as_of":"2026-11-12","source_name":"CSV A"},
                {"scheme_code":"456","nav":"12","as_of":"2026-11-13","source_name":"CSV B"},
                {"scheme_code":"789","nav":"13","as_of":"2026-11-13","source_name":"Unused"}])
        result=reconcile_funds(request,today=date(2026,11,14))
        codes={d["code"] for d in result["diagnostics"]}
        self.assertTrue({"MIXED_AS_OF_DATES","MULTIPLE_SOURCES","UNUSED_NAV_CODES",
                         "NO_RECORDED_VALUE","UNVERIFIED_PROVENANCE"}<=codes)
        self.assertEqual(result["quality_summary"]["unused_nav_scheme_codes"],["789"])
        self.assertFalse(result["portfolio_estimate_complete"])
        self.assertIsNone(result["portfolio_estimated_value"])
        self.assertIn("MIXED_AS_OF_DATES",{d["code"] for d in result["diagnostics"] if d["severity"]=="BLOCKER"})
    def test_missing_and_stale_blockers(self):
        request=FundReconciliationRequest(
            positions=[{"holding_id":1,"scheme_code":"123","units":"10","invested":"100"},
                       {"holding_id":2,"scheme_code":"456","units":"2","invested":"20"}],
            navs=[{"scheme_code":"123","nav":"11","as_of":"2026-10-01","source_name":"CSV"}])
        result=reconcile_funds(request,today=date(2026,11,14))
        blockers={d["code"] for d in result["diagnostics"] if d["severity"]=="BLOCKER"}
        self.assertEqual(blockers,{"MISSING_NAV","STALE_NAV"})
        self.assertIsNone(result["portfolio_estimated_value"])

if __name__=="__main__":unittest.main()
