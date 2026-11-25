from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.provider_router import ProviderFailure, Quote
from app.upstox_live_quote import current_quote


def configured():
    return SimpleNamespace(provider="UPSTOX", licensed_data_access=True,
                           entitlement_confirmed=True, upstox_token="test-token")


class UpstoxLiveQuoteTests(unittest.TestCase):
    def test_current_quote_returns_provider_price_and_timestamp(self):
        quote=Quote(symbol="RELIANCE",price="2500.25",
                    observed_at=datetime.now(timezone.utc),provider="UPSTOX")
        with patch("app.upstox_live_quote.settings",configured()), \
             patch("app.upstox_live_quote.upstox_quote",return_value=quote):
            result=current_quote("reliance","NSE_EQ|INE002A01018")
        self.assertEqual(result["price"],"2500.25")
        self.assertTrue(result["live"])
        self.assertEqual(result["source"],"UPSTOX")

    def test_stream_fallback_requires_exact_connected_fresh_key(self):
        from app.upstox_quote_worker import QuoteCache
        key="NSE_EQ|INE002A01018"
        cache=QuoteCache()
        cache.connected=True
        cache.quotes[key]={"instrument_key":key,"last_traded_price":2500.25,
                          "traded_at":datetime.now(timezone.utc).isoformat()}
        worker=SimpleNamespace(running=True,active_keys={key},cache=cache)
        with patch("app.upstox_live_quote.settings",configured()), \
             patch("app.upstox_live_quote.quote_worker",worker), \
             patch("app.upstox_live_quote.upstox_quote",side_effect=ProviderFailure("PROVIDER_RECOVERY_COOLDOWN")):
            result=current_quote("RELIANCE",key)
            self.assertTrue(result["fallback_used"])
            self.assertTrue(result["live_feed_verified"])
            self.assertEqual(result["transport"],"AUTHORIZED_UPSTOX_V3_STREAM")
            cache.connected=False
            with self.assertRaises(HTTPException):
                current_quote("RELIANCE",key)
            cache.connected=True
            worker.active_keys.clear()
            with self.assertRaises(HTTPException):
                current_quote("RELIANCE",key)
            worker.active_keys.add(key)
            cache.quotes[key]["traded_at"]=(datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat()
            with self.assertRaises(HTTPException):
                current_quote("RELIANCE",key)

    def test_current_quote_rejects_bad_mapping_and_provider_failure(self):
        with self.assertRaises(HTTPException) as invalid:
            current_quote("RELIANCE","bad-key")
        self.assertEqual(invalid.exception.status_code,422)
        with patch("app.upstox_live_quote.settings",configured()), \
             patch("app.upstox_live_quote.upstox_quote",side_effect=ProviderFailure("PROVIDER_REQUEST_FAILED")):
            with self.assertRaises(HTTPException) as failed:
                current_quote("RELIANCE","NSE_EQ|INE002A01018")
        self.assertEqual(failed.exception.status_code,502)


if __name__ == "__main__":
    unittest.main()
