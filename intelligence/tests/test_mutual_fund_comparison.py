import unittest
from datetime import date
from pydantic import ValidationError
from app.mutual_fund_history import NavHistoryImport
from app.mutual_fund_comparison import FundComparisonRequest,compare_funds

class ComparisonTests(unittest.TestCase):
    def fund(self,code,day="2025-01-31"):
        return NavHistoryImport(scheme_code=code,scheme_name="Fund "+code,source_name="User CSV",
            csv_text="scheme_code,as_of,nav\n"+code+",2025-01-01,10\n"+code+","+day+",11")
    def test_same_date(self):
        result=compare_funds(FundComparisonRequest(funds=[self.fund("123"),self.fund("456")]))
        self.assertTrue(result["same_latest_nav_date"])
        self.assertEqual(len(result["funds"]),2)
        self.assertIsNone(result["ratings"])
    def test_different_dates(self):
        result=compare_funds(FundComparisonRequest(funds=[self.fund("123"),self.fund("456","2025-02-01")]))
        self.assertFalse(result["same_latest_nav_date"])
        self.assertIsNone(result["rankings"])
    def test_duplicate_codes_rejected(self):
        with self.assertRaises(ValidationError):
            FundComparisonRequest(funds=[self.fund("123"),self.fund("123")])
    def test_bad_history_fails_closed(self):
        invalid=self.fund("456")
        invalid.csv_text="scheme_code,as_of,nav\n999,2025-01-01,10"
        with self.assertRaises(ValueError):
            compare_funds(FundComparisonRequest(funds=[self.fund("123"),invalid]))

if __name__=="__main__":unittest.main()
