import unittest
from datetime import datetime,timezone,timedelta
from copy import deepcopy
from app import company_venues as cv

NOW=datetime(2026,11,27,5,30,tzinfo=timezone.utc)
ISIN="INE002A01018"
def fixture():
    rows=[{"isin":ISIN,"id":1,"exchange":"NSE","symbol":"TEST","security_state":"NORMAL","as_of":"2026-11-26",
          "adjustment_status":"RAW_UNADJUSTED","turnover_first_date":"2026-10-28","turnover_dates_digest":"a"*64,"turnover_proxy_cr":20,"quote":None},
          {"isin":ISIN,"id":2,"exchange":"BSE","symbol":"TEST","security_state":"NORMAL","as_of":"2026-11-26",
          "adjustment_status":"RAW_UNADJUSTED","turnover_first_date":"2026-10-28","turnover_dates_digest":"a"*64,"turnover_proxy_cr":50,"quote":None}]
    matches=[{**r,"score":100-i} for i,r in enumerate(rows)]
    return rows,matches
def consolidate(rows,matches):
    return cv.consolidate(matches,{ISIN:rows},NOW,lambda r:-r["score"])
class CompanyVenueTests(unittest.TestCase):
    def test_one_company_and_historical_liquidity_preference(self):
        rows,matches=fixture()
        chosen=consolidate(rows,matches)
        self.assertEqual(len(chosen),1)
        self.assertEqual(chosen[0]["exchange"],"BSE")
        context=chosen[0]["company_venue_context"]
        self.assertEqual(context["status"],"HISTORICAL_TURNOVER_PREFERENCE")
        self.assertEqual(context["observed_venues"],["BSE","NSE"])
        self.assertFalse(context["execution_verified"])
    def test_fresh_paired_quote_overrides_historical_preference(self):
        rows,matches=fixture()
        for r,spread in zip(rows,(.1,.3)):
            r["quote"]={"observed_at":(NOW-timedelta(seconds=20)).isoformat(),"response_at":(NOW-timedelta(seconds=10)).isoformat(),
                "price":100,"spread_percent":spread,"turnover_proxy_cr":40}
        chosen=consolidate(rows,matches)[0]
        self.assertEqual(chosen["exchange"],"NSE")
        self.assertEqual(chosen["company_venue_context"]["status"],"PAIRED_QUOTE_LIQUIDITY_PREFERENCE")
        rows[0]["quote"]["observed_at"]=(NOW-timedelta(minutes=20)).isoformat()
        self.assertEqual(consolidate(rows,matches)[0]["exchange"],"BSE")
    def test_nonmatching_alternative_keeps_restriction_and_never_switches(self):
        rows,matches=fixture();rows[1]["security_state"]="SUSPENDED_REPORTED"
        chosen=consolidate(rows,matches[:1])[0]
        self.assertEqual(chosen["exchange"],"NSE")
        context=chosen["company_venue_context"]
        self.assertEqual(context["observed_venues"],["BSE","NSE"])
        self.assertIsNone(context["preferred_exchange"])
        self.assertIn("REPORTED_SUSPENDED_REPORTED_AT_BSE",context["review_findings"])
    def test_conflicting_identity_withheld_and_different_periods_not_compared(self):
        rows,matches=fixture()
        self.assertEqual(consolidate(rows+[{**rows[0],"id":3}],matches),[])
        rows[1]["as_of"]="2026-11-25"
        chosen=consolidate(rows,matches)[0]
        self.assertIsNone(chosen["company_venue_context"]["preferred_exchange"])
    def test_stale_venue_ignored(self):
        rows,_=fixture()
        snapshot={"sections":[{"section":"NSE","status":"READY","result":{"discovery_coverage":{"calendar_checked_on":"2026-11-27","calendar_status":"PUBLISHED_SESSION","expected_session":"2026-11-26"},"venue_observations":rows[:1]}},
            {"section":"BSE","status":"STALE","result":{"venue_observations":rows[1:]}}]}
        self.assertEqual(cv.collect(snapshot,NOW),{ISIN:rows[:1]})

    def test_historical_window_dates_must_match(self):
        rows,matches=fixture()
        rows[1]["turnover_dates_digest"]="b"*64
        chosen=consolidate(rows,matches)[0]
        self.assertEqual(chosen["exchange"],"NSE")
        self.assertIsNone(chosen["company_venue_context"]["preferred_exchange"])

    def test_horizon_selection_uses_same_policy_and_preserves_other_listing_warning(self):
        from app import stock_selection
        rows,matches=fixture()
        observations=[]
        for i,row in enumerate(matches):
            row.update(close=100,rank_score=100-i,adjustment_status="ADJUSTED")
            observations.append((row,{"status":"WITHHELD_EVIDENCE_GAPS","blockers":["FINAL_QUALIFICATION_VALIDATION_REQUIRED"],
                "review_findings":[],"gates":[{"domain":"TECHNICAL","status":"OBSERVATION_CHECKS_MET","requirements":[]}]}))
        # Historical comparison uses the venue observations, not transferred price levels.
        selection=stock_selection.summarize(observations,{"NSE","BSE"},{ISIN:rows},NOW)
        self.assertEqual(selection["watch_refs"],[{"exchange":"BSE","id":2,"isin":ISIN}])
        self.assertEqual(matches[1]["company_venue_context"]["preferred_exchange"],"BSE")
        rows[1]["security_state"]="SUSPENDED_REPORTED"
        selection=stock_selection.summarize(observations,{"NSE","BSE"},{ISIN:rows},NOW)
        self.assertEqual(selection["watch_refs"],[{"exchange":"NSE","id":1,"isin":ISIN}])
        self.assertIn("REPORTED_SUSPENDED_REPORTED_AT_BSE",matches[0]["selection_company_context"]["review_findings"])
