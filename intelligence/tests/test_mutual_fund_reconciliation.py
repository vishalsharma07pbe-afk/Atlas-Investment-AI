import unittest
from datetime import date
from pydantic import ValidationError
from app.mutual_fund_reconciliation import FundReconciliationRequest,reconcile_funds

class ReconciliationTests(unittest.TestCase):
    def payload(self):
        return {"positions":[{"holding_id":1,"scheme_code":"12345","units":"10.5","invested":"1000","recorded_value":"1050"},
                             {"holding_id":2,"scheme_code":"67890","units":"2","invested":"100"}],
                "navs":[{"scheme_code":"12345","nav":"110","as_of":"2026-11-13","source_name":"Local CSV"}]}
    def test_missing_is_not_fabricated(self):
        result=reconcile_funds(FundReconciliationRequest(**self.payload()),today=date(2026,11,14))
        self.assertEqual(result["matched_estimated_value"],"1155.0")
        self.assertEqual(result["rows"][0]["difference_from_recorded"],"105.0")
        self.assertIsNone(result["portfolio_estimated_value"])
        self.assertEqual(result["missing_nav_positions"],1)
    def test_complete(self):
        data=self.payload()
        data["navs"].append({"scheme_code":"67890","nav":"60","as_of":"2026-11-13","source_name":"Local CSV"})
        result=reconcile_funds(FundReconciliationRequest(**data),today=date(2026,11,14))
        self.assertTrue(result["portfolio_estimate_complete"])
        self.assertEqual(result["portfolio_estimated_value"],"1275.0")
    def test_stale_blocks_complete(self):
        data=self.payload()
        data["positions"]=data["positions"][:1]
        data["navs"][0]["as_of"]="2026-10-01"
        result=reconcile_funds(FundReconciliationRequest(**data),today=date(2026,11,14))
        self.assertFalse(result["portfolio_estimate_complete"])
        self.assertEqual(result["stale_nav_positions"],1)
    def test_duplicate_navs_rejected(self):
        data=self.payload();data["navs"].append(data["navs"][0])
        with self.assertRaises(ValidationError):FundReconciliationRequest(**data)

if __name__=="__main__":unittest.main()
