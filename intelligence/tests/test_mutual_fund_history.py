import unittest
from datetime import date
from unittest.mock import patch
from app.mutual_fund_history import NavHistoryImport,import_nav_history

class HistoryTests(unittest.TestCase):
    def request(self,rows):
        return NavHistoryImport(scheme_code="12345",scheme_name="Example Fund",source_name="Local CSV",
                                csv_text="scheme_code,as_of,nav\n"+rows)
    def test_success(self):
        result=import_nav_history(self.request("12345,2025-01-01,10\n12345,2025-01-31,11"))
        self.assertEqual(result["import"]["rows_accepted"],2)
        self.assertFalse(result["import"]["stored"])
        self.assertEqual(result["source"]["verification"],"USER_SUPPLIED_UNVERIFIED")
    def test_bad_rows(self):
        for rows in ("99999,2025-01-01,10","12345,2025-01-01,0",
                     "12345,2025-02-01,10\n12345,2025-01-01,11",
                     "12345,2025-01-01,10\n12345,2025-01-01,11",
                     "12345,2025-01-01,NaN","12345,invalid,10"):
            with self.subTest(rows=rows):
                with self.assertRaises(ValueError):import_nav_history(self.request(rows))
    def test_empty(self):
        with self.assertRaises(ValueError):import_nav_history(self.request(""))

if __name__=="__main__":unittest.main()
