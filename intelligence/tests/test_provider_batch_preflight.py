import unittest
from datetime import date
from pydantic import ValidationError
from app.provider_batch_preflight import BatchPreflightRequest,preflight_batch

class BatchPreflightTests(unittest.TestCase):
    def payload(self):
        return {"provider":"UPSTOX","source_reference":"authorized test fixture",
                "rights_confirmed":True,"entitlement_confirmed":True,
                "instrument_mapping_confirmed":True,
                "candles":[{"instrument_key":"NSE_EQ|123","trade_date":"2026-11-13",
                            "open":"100","high":"110","low":"90","close":"105","volume":100}]}
    def test_never_authorizes_ingestion(self):
        result=preflight_batch(BatchPreflightRequest(**self.payload()),today=date(2026,11,14))
        self.assertEqual(result["status"],"BLOCKED")
        self.assertFalse(result["ingestion_authorized"])
        self.assertIn("PROVIDER_ADAPTER_NOT_VERIFIED",result["blockers"])
    def test_missing_rights_blocked(self):
        data=self.payload();data["rights_confirmed"]=False
        result=preflight_batch(BatchPreflightRequest(**data),today=date(2026,11,14))
        self.assertIn("DATA_USAGE_RIGHTS_UNCONFIRMED",result["blockers"])
    def test_duplicate_blocked(self):
        data=self.payload();data["candles"].append(data["candles"][0])
        result=preflight_batch(BatchPreflightRequest(**data),today=date(2026,11,14))
        self.assertIn("DUPLICATE_INSTRUMENT_DATE",result["blockers"])
    def test_stale_blocked(self):
        data=self.payload();data["candles"][0]["trade_date"]="2026-10-01"
        result=preflight_batch(BatchPreflightRequest(**data),today=date(2026,11,14))
        self.assertIn("STALE_INSTRUMENT_OVER_3_CALENDAR_DAYS",result["blockers"])
    def test_bad_ohlc_rejected(self):
        data=self.payload();data["candles"][0]["high"]="99"
        with self.assertRaises(ValidationError):BatchPreflightRequest(**data)

if __name__=="__main__":unittest.main()
