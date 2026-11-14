import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from app import multi_provider_quotes as multi

class MultiProviderTests(unittest.TestCase):
    def test_offline_fails_closed(self):
        with patch.dict("os.environ", {"UPSTOX_ACCESS_TOKEN":"", "ATLAS_POLYGON_API_KEY":"",
                                     "ATLAS_UPSTOX_QUOTES_AUTHORIZED":"false",
                                     "ATLAS_POLYGON_QUOTES_AUTHORIZED":"false"}, clear=False):
            result = multi.quote_status("RELIANCE")
            self.assertEqual(result["status"], "UNAVAILABLE")
            self.assertIsNone(result["quote"])
            self.assertEqual(len(result["attempts"]), 2)
    def test_upstox_quote_schema(self):
        stamp = int(datetime.now(timezone.utc).timestamp() * 1000)
        with patch.object(multi, "_request", return_value={"status":"success","data":{
            "NSE_EQ|INE002A01018":{"instrument_token":"NSE_EQ|INE002A01018",
                                  "last_price":123.45,"last_trade_time":stamp}}}):
            quote = multi.upstox_quote("RELIANCE","NSE_EQ|INE002A01018","dummy")
            self.assertEqual(quote.price,"123.45")
            self.assertEqual(quote.symbol,"RELIANCE")
    def test_upstox_instrument_mismatch(self):
        with patch.object(multi, "_request", return_value={"status":"success","data":{
            "bad":{"instrument_token":"NSE_EQ|WRONG","last_price":123,"last_trade_time":1700000000000}}}):
            with self.assertRaises(multi.ProviderFailure):
                multi.upstox_quote("RELIANCE","NSE_EQ|INE002A01018","dummy")
    def test_fallback_after_primary_error(self):
        stamp = int(datetime.now(timezone.utc).timestamp() * 1_000_000_000)
        def fake_request(url, headers):
            if "upstox.com" in url:
                raise multi.ProviderFailure("UNAVAILABLE")
            return {"status":"OK","results":{"T":"AAPL","p":180.25,"t":stamp}}
        with patch.object(multi,"_request",side_effect=fake_request), patch.dict("os.environ",{
            "UPSTOX_ACCESS_TOKEN":"dummy","ATLAS_POLYGON_API_KEY":"dummy",
            "ATLAS_UPSTOX_SYMBOL_MAP":'{"AAPL":"NSE_EQ|TEST"}',
            "ATLAS_UPSTOX_QUOTES_AUTHORIZED":"true",
            "ATLAS_POLYGON_QUOTES_AUTHORIZED":"true",
            "ATLAS_POLYGON_US_SYMBOLS":"AAPL"},clear=False):
            result = multi.quote_status("AAPL")
            self.assertEqual(result["status"],"VALIDATED")
            self.assertEqual(result["quote"]["source"],"POLYGON")
            self.assertFalse(result["live_feed_verified"])
    def test_reject_naive_time(self):
        with self.assertRaises(multi.ProviderFailure):
            multi._timestamp("2026-11-14T12:00:00")
if __name__ == "__main__":
    unittest.main()
