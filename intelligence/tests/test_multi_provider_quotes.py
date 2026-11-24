import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from app import multi_provider_quotes as multi

class MultiProviderTests(unittest.TestCase):
    def setUp(self):
        stub=patch.object(multi,"quote_breaker",multi.CircuitBreaker())
        stub.start()
        self.addCleanup(stub.stop)
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
    def test_upstox_access_rejection_is_distinguishable(self):
        denied=Mock(status_code=403)
        with patch.object(multi.httpx,"get",return_value=denied):
            with self.assertRaisesRegex(multi.ProviderFailure,"PROVIDER_ACCESS_REJECTED"):
                multi._request("https://api.upstox.com",{})
    def test_request_identifies_atlas_to_provider(self):
        response=Mock(status_code=200,content=b'{"status":"success"}')
        with patch.object(multi.httpx,"get",return_value=response) as get:
            multi._request("https://api.upstox.com",{"Accept":"application/json"})
        self.assertEqual(get.call_args.kwargs["headers"]["User-Agent"],"ATLAS-Research/1.0")
    def test_ambiguous_cross_market_identity_never_routes(self):
        stamp = int(datetime.now(timezone.utc).timestamp() * 1_000_000_000)
        def fake_request(url, headers):
            if "upstox.com" in url:
                raise multi.ProviderFailure("UNAVAILABLE")
            return {"status":"OK","results":{"T":"AAPL","p":180.25,"t":stamp}}
        with patch.object(multi,"_request",side_effect=fake_request) as request, patch.dict("os.environ",{
            "UPSTOX_ACCESS_TOKEN":"dummy","ATLAS_POLYGON_API_KEY":"dummy",
            "ATLAS_UPSTOX_SYMBOL_MAP":'{"AAPL":"NSE_EQ|TEST"}',
            "ATLAS_UPSTOX_QUOTES_AUTHORIZED":"true",
            "ATLAS_POLYGON_QUOTES_AUTHORIZED":"true",
            "ATLAS_POLYGON_US_SYMBOLS":"AAPL"},clear=False):
            result = multi.quote_status("AAPL")
            self.assertEqual(result["status"],"UNAVAILABLE")
            self.assertEqual(result["reason"],"AMBIGUOUS_MARKET_IDENTITY")
            request.assert_not_called()
    def test_access_rejection_opens_shared_circuit_across_requests(self):
        with patch.dict("os.environ",{"UPSTOX_ACCESS_TOKEN":"dummy","ATLAS_UPSTOX_SYMBOL_MAP":'{"RELIANCE":"NSE_EQ|INE002A01018"}',
                                     "ATLAS_UPSTOX_QUOTES_AUTHORIZED":"true","ATLAS_POLYGON_US_SYMBOLS":""}), \
             patch.object(multi,"_request",side_effect=multi.ProviderFailure("PROVIDER_ACCESS_REJECTED")) as request:
            first=multi.quote_status("RELIANCE")
            second=multi.quote_status("RELIANCE")
            self.assertEqual(first["attempts"][0]["reason"],"PROVIDER_ACCESS_REJECTED")
            self.assertEqual(second["attempts"][0]["status"],"CIRCUIT_OPEN")
            request.assert_called_once()
    def test_reject_naive_time(self):
        with self.assertRaises(multi.ProviderFailure):
            multi._timestamp("2026-11-14T12:00:00")
    def test_accepts_provider_epoch_milliseconds_as_string(self):
        value = str(int(datetime.now(timezone.utc).timestamp() * 1000))
        self.assertIsNotNone(multi._timestamp(value).tzinfo)
if __name__ == "__main__":
    unittest.main()
