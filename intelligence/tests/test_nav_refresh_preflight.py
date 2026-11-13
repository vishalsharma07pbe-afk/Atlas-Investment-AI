import unittest
from datetime import date
from pydantic import ValidationError
from app.nav_refresh_preflight import NavRefreshPreflightRequest,preflight_nav_refresh

class NavRefreshPreflightTests(unittest.TestCase):
    def payload(self):
        return {"source_name":"Authorized local export","source_authorized":True,
                "expected_scheme_codes":["123","456"],
                "records":[{"scheme_code":"123","nav":"10.5","as_of":"2026-11-13"},
                           {"scheme_code":"456","nav":"20","as_of":"2026-11-13"}]}
    def test_valid_is_review_only(self):
        result=preflight_nav_refresh(NavRefreshPreflightRequest(**self.payload()),today=date(2026,11,14))
        self.assertEqual(result["status"],"READY_FOR_MANUAL_REVIEW")
        self.assertFalse(result["stored"])
        self.assertFalse(result["refresh_executed"])
    def test_not_authorized_is_blocked(self):
        data=self.payload();data["source_authorized"]=False
        result=preflight_nav_refresh(NavRefreshPreflightRequest(**data),today=date(2026,11,14))
        self.assertIn("SOURCE_AUTHORIZATION_NOT_CONFIRMED",result["blockers"])
    def test_mixed_dates_are_blocked(self):
        data=self.payload();data["records"][1]["as_of"]="2026-11-12"
        result=preflight_nav_refresh(NavRefreshPreflightRequest(**data),today=date(2026,11,14))
        self.assertIn("MIXED_VALUATION_DATES",result["blockers"])
    def test_duplicates_missing_and_unexpected(self):
        data=self.payload()
        data["records"]=[data["records"][0],data["records"][0],{"scheme_code":"999","nav":"10","as_of":"2026-11-13"}]
        result=preflight_nav_refresh(NavRefreshPreflightRequest(**data),today=date(2026,11,14))
        self.assertTrue({"DUPLICATE_SCHEME_CODES","MISSING_EXPECTED_SCHEMES","UNEXPECTED_SCHEME_CODES"}<=set(result["blockers"]))
    def test_future_and_stale(self):
        data=self.payload();data["records"][0]["as_of"]="2026-11-15";data["records"][1]["as_of"]="2026-10-01"
        result=preflight_nav_refresh(NavRefreshPreflightRequest(**data),today=date(2026,11,14))
        self.assertTrue({"FUTURE_NAV_DATES","STALE_NAV_DATES"}<=set(result["blockers"]))
    def test_nonfinite_rejected(self):
        data=self.payload();data["records"][0]["nav"]="Infinity"
        with self.assertRaises(ValidationError):NavRefreshPreflightRequest(**data)

if __name__=="__main__":unittest.main()
