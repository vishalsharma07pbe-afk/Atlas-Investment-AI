import unittest
from pydantic import ValidationError
from app.mutual_fund_nav import NavPoint
from app.mutual_fund_history import NavHistoryImport,import_nav_history
from app.mutual_fund_reconciliation import FundPosition,FundNav

class NumericValidationTests(unittest.TestCase):
    def test_nonfinite_nav_point(self):
        for value in ("NaN","Infinity","-Infinity"):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    NavPoint(as_of="2025-01-01",nav=value)
    def test_nonfinite_portfolio_numbers(self):
        for field in ("units","invested","recorded_value"):
            for value in ("NaN","Infinity","-Infinity"):
                with self.subTest(field=field,value=value):
                    payload={"holding_id":1,"scheme_code":"12345","units":"10","invested":"100","recorded_value":"110"}
                    payload[field]=value
                    with self.assertRaises(ValidationError):FundPosition(**payload)
        for value in ("NaN","Infinity","-Infinity"):
            with self.assertRaises(ValidationError):
                FundNav(scheme_code="12345",nav=value,as_of="2025-01-01",source_name="Local")
    def test_csv_overflow_rejected(self):
        request=NavHistoryImport(scheme_code="12345",scheme_name="Fund",source_name="Local",
            csv_text="scheme_code,as_of,nav\n12345,2025-01-01,1e10000")
        with self.assertRaises(ValueError):import_nav_history(request)

if __name__=="__main__":unittest.main()
