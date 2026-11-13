import unittest
from datetime import date
from pydantic import ValidationError
from app.mutual_fund_scheme_search import SchemeSearchRequest,search_schemes

def row(code,name,nav="10.5",stamp="13-Nov-2026"):
    return f"{code};ISIN1;ISIN2;{name};{nav};{stamp}"

class SchemeSearchTests(unittest.TestCase):
    def search(self,lines,query="growth",limit=20):
        return search_schemes(SchemeSearchRequest(text="\n".join(lines),query=query,limit=limit),today=date(2026,11,14))
    def test_name_search_and_limit(self):
        data=self.search([row("12345","Alpha Growth"),row("67890","Beta Growth"),row("99999","Other")],limit=1)
        self.assertEqual(data["matches_total"],2)
        self.assertTrue(data["truncated"])
        self.assertEqual(data["schemes"][0]["scheme_code"],"12345")
        self.assertEqual(data["source"]["verification"],"USER_SUPPLIED_UNVERIFIED")
    def test_exact_code_substring_search(self):
        data=self.search([row("12345","Alpha Fund")],query="12345")
        self.assertEqual(data["schemes"][0]["scheme_name"],"Alpha Fund")
    def test_rejects_duplicate_matching_scheme(self):
        data=self.search([row("12345","Alpha Growth"),row("12345","Alpha Growth")])
        self.assertEqual(data["schemes"],[])
        self.assertEqual(data["duplicate_scheme_codes"],["12345"])
    def test_rejects_invalid_and_future_nav(self):
        data=self.search([row("12345","Alpha Growth","NaN"),row("23456","Beta Growth","10","15-Nov-2026"),row("34567","Gamma Growth","1e999999")])
        self.assertEqual(data["schemes"],[])
    def test_bounds(self):
        with self.assertRaises(ValidationError):
            SchemeSearchRequest(text="x",query=" ",limit=20)
        with self.assertRaises(ValidationError):
            SchemeSearchRequest(text="x",query="growth",limit=51)

if __name__=="__main__":unittest.main()
