import unittest
from datetime import date,timedelta
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import HTTPException
from pydantic import ValidationError
from app import provider_batch as batch

TODAY=date(2026,11,13)
KEYS=["NSE_EQ|INE848E01016","BSE_EQ|INE848E01016"]

def request(keys=None):
    return batch.BatchRequest(instrument_keys=keys or KEYS,
        from_date=date(2026,11,1),to_date=date(2026,11,13),max_age_days=7)

class ProviderBatchTests(unittest.TestCase):
    def test_batch_review_pacing_and_quality_gates(self):
        starts=[]
        current=[0.0]
        def clock():return current[0]
        def pause(duration):current[0]+=duration
        def fetch(key,first,last):
            starts.append(current[0])
            return {"candles":[{"trade_date":"2026-11-12"}]}
        settings=SimpleNamespace(provider="UPSTOX",licensed_data_access=True,
            entitlement_confirmed=True,upstox_token="secret",request_rate_per_second=2)
        with patch.object(batch,"settings",settings):
            result=batch.review_batch(request(),fetch=fetch,now=TODAY,clock=clock,pause=pause)
        self.assertEqual(result["succeeded"],2)
        self.assertEqual(starts,[0,0.5])
        self.assertFalse(result["automatic_ingestion_enabled"])
        self.assertNotIn("secret",str(result))
        self.assertIn("ADJUSTMENT_UNVERIFIED",result["results"][0]["quality_flags"])
        self.assertNotIn("candles",result["results"][0])

    def test_stale_and_partial_failure(self):
        def fetch(key,first,last):
            if key==KEYS[1]:raise HTTPException(status_code=429,detail="private provider detail")
            return {"candles":[{"trade_date":"2026-11-01"}]}
        settings=SimpleNamespace(provider="UPSTOX",licensed_data_access=True,
            entitlement_confirmed=True,upstox_token="secret",request_rate_per_second=5)
        with patch.object(batch,"settings",settings):
            result=batch.review_batch(request(),fetch=fetch,now=TODAY,clock=lambda:0,pause=lambda _:None)
        self.assertEqual(result["failed"],1)
        self.assertIn("STALE_OR_FUTURE_CANDLES",result["results"][0]["quality_flags"])
        self.assertNotIn("private provider detail",str(result))

    def test_duplicate_and_invalid_keys_fail_validation(self):
        with self.assertRaises(ValidationError):
            request([KEYS[0],KEYS[0]])
        with self.assertRaises(ValidationError):
            request(["https://example.org/"])
        with self.assertRaises(ValidationError):
            request(KEYS*3)

    def test_disabled_provider_never_fetches(self):
        settings=SimpleNamespace(provider="MANUAL_CSV",licensed_data_access=False,
            entitlement_confirmed=False,upstox_token=None,request_rate_per_second=1)
        with patch.object(batch,"settings",settings):
            with self.assertRaises(HTTPException) as exc:
                batch.review_batch(request(),fetch=lambda *a:self.fail("unexpected network"))
            self.assertEqual(exc.exception.status_code,403)

if __name__=="__main__":unittest.main()
