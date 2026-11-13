import unittest
from datetime import date
from pydantic import ValidationError
from app.provider_reconciliation import ReconciliationRequest,reconcile

def sample():
    return {"mapping":{"instrument_key":"NSE_EQ|INE848E01016","exchange":"NSE",
            "symbol":"EXAMPLE","series":"EQ","isin":"INE848E01016",
            "adjustment_verified":True,"sessions_verified":True,"usage_rights_verified":True},
        "registry_exchange":"NSE","registry_symbol":"EXAMPLE","registry_series":"EQ",
        "registry_isin":"INE848E01016","provider_source_revision":"user-review-1",
        "known_session_dates":["2026-11-11","2026-11-12"],
        "candles":[{"trade_date":"2026-11-11","open":100,"high":105,"low":99,"close":103,"volume":1000,
            "adjustment_status":"RAW_UNADJUSTED"},
            {"trade_date":"2026-11-12","open":103,"high":108,"low":101,"close":106,"volume":1200,
            "adjustment_status":"RAW_UNADJUSTED"}]}

class ReconciliationTests(unittest.TestCase):
    def test_even_matching_declarations_require_independent_audit(self):
        result=reconcile(ReconciliationRequest.model_validate(sample()),as_of=date(2026,11,13))
        self.assertEqual(result["status"],"BLOCKED_FROM_AUTOMATIC_INGESTION")
        self.assertEqual(result["blockers"],["INDEPENDENT_PROVENANCE_AUDIT_REQUIRED"])
        self.assertEqual(result["unmatched_session_count"],0)

    def test_mapping_sessions_and_adjustment_fail_closed(self):
        data=sample()
        data["registry_symbol"]="OTHER"
        data["known_session_dates"]=[]
        data["mapping"]["adjustment_verified"]=False
        data["candles"][0]["adjustment_status"]="UNVERIFIED"
        result=reconcile(ReconciliationRequest.model_validate(data),as_of=date(2026,11,13))
        for blocker in ("REGISTRY_MAPPING_MISMATCH","MISSING_VERIFIED_SESSION_DATES",
            "CORPORATE_ACTION_ADJUSTMENT_NOT_VERIFIED","CANDLE_ADJUSTMENT_UNVERIFIED",
            "MIXED_ADJUSTMENT_STATUS"):
            self.assertIn(blocker,result["blockers"])

    def test_duplicate_dates_and_future(self):
        data=sample()
        data["candles"][1]["trade_date"]="2026-11-11"
        result=reconcile(ReconciliationRequest.model_validate(data),as_of=date(2026,11,10))
        self.assertIn("DUPLICATE_CANDLE_DATE",result["blockers"])
        self.assertIn("FUTURE_CANDLES",result["blockers"])

    def test_invalid_price_rejected(self):
        data=sample()
        data["candles"][0]["high"]=90
        with self.assertRaises(ValidationError):
            ReconciliationRequest.model_validate(data)

if __name__=="__main__":unittest.main()
