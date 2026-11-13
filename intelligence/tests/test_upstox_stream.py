import unittest
from app.upstox_stream import StreamPolicy,validate_redirect,subscription_request,normalize_tick,stream_readiness

class UpstoxStreamTests(unittest.TestCase):
    def test_secure_redirect(self):
        url="wss://feed.upstox.com/market-data-feeder/v3?code=secret"
        self.assertEqual(validate_redirect(url),url)
        for bad in ["ws://feed.upstox.com/a","wss://upstox.com.evil.test/a","wss://evil.test/a",
                    "wss://user:pass@feed.upstox.com/a","wss://feed.upstox.com:8443/a"]:
            with self.assertRaises(ValueError):validate_redirect(bad)

    def test_subscription_limits(self):
        p=StreamPolicy()
        request=subscription_request(["NSE_EQ|INE002A01018"],p,"test-guid")
        self.assertEqual(request["data"]["mode"],"ltpc")
        with self.assertRaises(ValueError):
            subscription_request(["NSE_EQ|INE002A01018"]*2,p,"test-guid")

    def test_fresh_and_stale_ticks(self):
        p=StreamPolicy(max_tick_age_seconds=15)
        good=normalize_tick("NSE_EQ|INE002A01018",{"ltp":100.25,"ltt":"1000000"},p,now_ms=1001000)
        self.assertEqual(good["status"],"FRESH")
        with self.assertRaises(ValueError):
            normalize_tick("NSE_EQ|INE002A01018",{"ltp":100.25,"ltt":"1000000"},p,now_ms=1100000)
        with self.assertRaises(ValueError):
            normalize_tick("NSE_EQ|INE002A01018",{"ltp":float("nan"),"ltt":"1000000"},p,now_ms=1001000)

    def test_never_claim_live_without_connection(self):
        self.assertEqual(stream_readiness(True,True,False,False)["status"],"BLOCKED")
        self.assertFalse(stream_readiness(True,True,False,False)["live_quotes_available"])

if __name__=="__main__":unittest.main()
