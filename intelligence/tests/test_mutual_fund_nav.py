import unittest
from datetime import date,timedelta
from pydantic import ValidationError
from app.mutual_fund_nav import FundNavRequest,analyze_nav

class NavTests(unittest.TestCase):
    def make(self,values,dates=None):
        dates=dates or [date(2025,1,1)+timedelta(days=i*30) for i in range(len(values))]
        return FundNavRequest(scheme_code="12345",scheme_name="Example scheme",source_name="User CSV",
            navs=[{"as_of":d,"nav":v} for d,v in zip(dates,values)])
    def test_returns_without_inventing_history(self):
        request=self.make([10,11,12,13])
        result=analyze_nav(request,today=date(2025,4,1))
        self.assertEqual(result["latest_nav"]["nav"],13)
        self.assertAlmostEqual(result["trailing_returns_pct"]["1m"],(13/12-1)*100,places=4)
        self.assertIsNone(result["trailing_returns_pct"]["1y"])
        self.assertIsNone(result["ratings"])
    def test_stale_and_missing(self):
        result=analyze_nav(self.make([10]),today=date(2026,1,1))
        self.assertEqual(result["latest_nav"]["status"],"STALE")
        self.assertTrue(all(x is None for x in result["trailing_returns_pct"].values()))
    def test_duplicate_unsorted_and_invalid(self):
        for navs in ([{"as_of":"2025-01-01","nav":10},{"as_of":"2025-01-01","nav":11}],
                     [{"as_of":"2025-02-01","nav":10},{"as_of":"2025-01-01","nav":11}],
                     [{"as_of":"2025-01-01","nav":0}]):
            with self.assertRaises(ValidationError):
                FundNavRequest(scheme_code="123",scheme_name="Test",source_name="CSV",navs=navs)
    def test_bad_source_url(self):
        with self.assertRaises(ValidationError):
            FundNavRequest(scheme_code="123",scheme_name="Test",source_name="CSV",
                source_url="http://example.org",navs=[{"as_of":"2025-01-01","nav":10}])

if __name__=="__main__":unittest.main()
