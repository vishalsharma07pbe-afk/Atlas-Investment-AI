import unittest
from datetime import date
from app.amfi_nav_import import parse_amfi

ROW="12345;INF000000001;INF000000002;Sample Direct Growth;123.4567;12-Nov-2026"
class AmfiTests(unittest.TestCase):
    def test_parses_selected_scheme(self):
        result=parse_amfi("Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date\n"+ROW,["12345"],date(2026,11,13))
        self.assertEqual(result["schemes"][0]["nav"],123.4567)
        self.assertEqual(result["schemes"][0]["age_days"],1)
        self.assertFalse(result["historical_returns_available"])
    def test_rejects_invalid_and_missing(self):
        result=parse_amfi(ROW.replace("123.4567","N.A."),["12345","99999"],date(2026,11,13))
        self.assertEqual(result["schemes"],[])
        self.assertEqual(result["missing_scheme_codes"],["12345","99999"])
    def test_future_date_and_duplicates(self):
        self.assertEqual(parse_amfi(ROW.replace("12-Nov-2026","14-Nov-2026"),["12345"],date(2026,11,13))["schemes"],[])
        self.assertEqual(parse_amfi(ROW+"\n"+ROW,["12345"],date(2026,11,13))["schemes"],[])
    def test_rejects_bad_scheme_ids(self):
        with self.assertRaises(ValueError):parse_amfi(ROW,["../123"])
        with self.assertRaises(ValueError):parse_amfi(ROW,["12345","12345"])

if __name__=="__main__":unittest.main()
