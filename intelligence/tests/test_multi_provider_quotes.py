import unittest
import tempfile
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from app import multi_provider_quotes as multi

class MultiProviderTests(unittest.TestCase):
    def setUp(self):
        root=tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        env=patch.dict('os.environ',{'ATLAS_QUOTE_RECOVERY_DB':root.name+'/recovery.sqlite'})
        env.start()
        self.addCleanup(env.stop)
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
        self.assertEqual(get.call_args.kwargs["headers"]["User-Agent"],"ATLAS/2.0")
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
    def test_dhan_fallback_exact_mapping_and_read_only_post(self):
        now=datetime.now(timezone.utc).isoformat()
        with patch.dict("os.environ",{
            "UPSTOX_ACCESS_TOKEN":"dummy","ATLAS_UPSTOX_SYMBOL_MAP":'{"RELIANCE":"NSE_EQ|INE002A01018"}',
            "ATLAS_UPSTOX_QUOTES_AUTHORIZED":"true","ATLAS_DHAN_QUOTES_AUTHORIZED":"true",
            "ATLAS_DHAN_ACCESS_TOKEN":"secret","ATLAS_DHAN_CLIENT_ID":"client",
            "ATLAS_DHAN_SYMBOL_MAP":'{"RELIANCE":{"upstox_key":"NSE_EQ|INE002A01018","security_id":123}}',
            "ATLAS_POLYGON_US_SYMBOLS":""}),patch.object(multi.httpx,"get",return_value=Mock(status_code=403)) as get, \
            patch.object(multi.httpx,"post",return_value=Mock(status_code=200,content=__import__("json").dumps(
                {"status":"success","data":{"NSE_EQ":{"123":{"last_price":150,"last_trade_time":now}}}}).encode())) as post:
            result=multi.quote_status("RELIANCE")
            self.assertEqual(result["quote"]["source"],"DHAN")
            self.assertEqual(result["quote"]["price"],"150")
            self.assertFalse(result["live_feed_verified"])
            get.assert_called_once()
            post.assert_called_once()
            self.assertEqual(post.call_args.args[0],"https://api.dhan.co/v2/marketfeed/quote")
            self.assertEqual(post.call_args.kwargs["json"],{"NSE_EQ":[123]})
            self.assertFalse(post.call_args.kwargs["follow_redirects"])
            self.assertNotIn("secret",str(result))
            self.assertTrue(multi.provider_status()["same_market_fallback_configured"])
            self.assertFalse(multi.provider_status()["automatic_fallback_available"])
            self.assertEqual(result["route"]["status"],"SAME_MARKET_FALLBACK")
            self.assertEqual(result["quote"]["currency"],"INR")
            self.assertEqual(result["quote"]["instrument_key"],"NSE_EQ|INE002A01018")
            evidence=multi.provider_status()["fallback_observation"]
            self.assertEqual(evidence["status"],"PAST_VALIDATED_HTTP_FALLBACK")
            self.assertEqual(evidence["observation_count"],1)
            self.assertNotIn("INE002A01018",str(evidence))
    def test_dhan_rejects_unverified_naive_time_and_mismatched_identity(self):
        body={"status":"success","data":{"NSE_EQ":{"123":{"last_price":150,"last_trade_time":"26/11/2026 15:00:00"}}}}
        with patch.object(multi,"_request",return_value=body):
            with self.assertRaisesRegex(multi.ProviderFailure,"DHAN_TIMESTAMP_UNVERIFIED"):
                multi.dhan_quote("RELIANCE","NSE_EQ|INE002A01018",123,"token","client")
            quote=multi.dhan_quote("RELIANCE","NSE_EQ|INE002A01018",123,"token","client",confirmed_ist=True)
            self.assertEqual(quote.observed_at.isoformat(),"2026-11-26T09:30:00+00:00")
            with self.assertRaisesRegex(multi.ProviderFailure,"DHAN_INSTRUMENT_MISMATCH"):
                multi.dhan_quote("RELIANCE","BSE_EQ|INE002A01018",123,"token","client",confirmed_ist=True)
    def test_dhan_mapping_conflict_and_unapproved_transport_fail_closed(self):
        mapping={"A":"NSE_EQ|INE002A01018","B":"NSE_EQ|INE009A01021"}
        with patch.dict("os.environ",{"ATLAS_DHAN_SYMBOL_MAP":'{"A":{"upstox_key":"NSE_EQ|INE002A01018","security_id":1},"B":{"upstox_key":"NSE_EQ|INE009A01021","security_id":1}}'}):
            self.assertEqual(multi._dhan_mapping(mapping),{})
        with patch.object(multi.httpx,"post") as post:
            with self.assertRaises(multi.ProviderFailure):
                multi._request("https://api.dhan.co/v2/orders",{},payload={})
            post.assert_not_called()

    def test_duplicate_json_keys_and_non_equity_identity_are_rejected(self):
        with patch.dict("os.environ",{"ATLAS_UPSTOX_SYMBOL_MAP":'{"A":"NSE_EQ|INE002A01018","A":"BSE_EQ|INE002A01018"}'}):
            self.assertEqual(multi._mapping(),{})
        with patch.object(multi,"_request") as request:
            with self.assertRaises(multi.ProviderFailure):
                multi.upstox_quote("NIFTY","NSE_INDEX|Nifty50","test")
            request.assert_not_called()

    def test_direct_dhan_is_not_recorded_as_failover(self):
        with patch.dict("os.environ",{
            "ATLAS_UPSTOX_QUOTES_AUTHORIZED":"false","ATLAS_UPSTOX_SYMBOL_MAP":'{"A":"NSE_EQ|INE002A01018"}',
            "ATLAS_DHAN_QUOTES_AUTHORIZED":"true","ATLAS_DHAN_ACCESS_TOKEN":"test","ATLAS_DHAN_CLIENT_ID":"test",
            "ATLAS_DHAN_SYMBOL_MAP":'{"A":{"upstox_key":"NSE_EQ|INE002A01018","security_id":123}}',
            "ATLAS_POLYGON_US_SYMBOLS":""}),patch.object(multi,"dhan_quote",return_value=multi.Quote("A","100",datetime.now(timezone.utc),"DHAN")):
            result=multi.quote_status("A")
        self.assertEqual(result["route"]["status"],"DIRECT_PROVIDER")
        self.assertEqual(multi.quote_recovery.fallback_status()["status"],"NOT_OBSERVED")

if __name__ == "__main__":
    unittest.main()
