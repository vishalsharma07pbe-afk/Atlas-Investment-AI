import unittest
from datetime import datetime,timezone,timedelta
from app.provider_router import Quote,ReadOnlyRouter,CircuitBreaker,readiness

NOW=datetime(2026,11,14,6,0,tzinfo=timezone.utc)
class ProviderRouterTests(unittest.TestCase):
    def q(self,price="100",seconds=0,symbol="RELIANCE"):
        return Quote(symbol,price,NOW-timedelta(seconds=seconds),"test")
    def test_fallback_when_primary_fails(self):
        router=ReadOnlyRouter([("primary",lambda s: (_ for _ in ()).throw(RuntimeError("offline")),True),
                               ("backup",lambda s:self.q(),True)],clock=lambda:NOW)
        r=router.quote("RELIANCE")
        self.assertEqual(r["status"],"VALIDATED")
        self.assertEqual(r["quote"]["source"],"backup")
        self.assertFalse(r["live"])
    def test_unlicensed_never_called(self):
        calls=[]
        router=ReadOnlyRouter([("blocked",lambda s:calls.append(s),False)],clock=lambda:NOW)
        self.assertEqual(router.quote("RELIANCE")["status"],"UNAVAILABLE")
        self.assertEqual(calls,[])
    def test_stale_negative_future_and_mismatched_rejected(self):
        for quote in (self.q(seconds=70),self.q(price="-1"),self.q(price="NaN"),
                      self.q(seconds=-1),self.q(symbol="OTHER")):
            router=ReadOnlyRouter([("bad",lambda s,q=quote:q,True)],clock=lambda:NOW)
            self.assertEqual(router.quote("RELIANCE")["status"],"UNAVAILABLE")
    def test_circuit_breaker_and_recovery(self):
        ticks=[0]
        breaker=CircuitBreaker(threshold=2,cooldown_seconds=30,clock=lambda:ticks[0])
        breaker.failure("x");breaker.failure("x")
        self.assertFalse(breaker.allow("x"))
        ticks[0]=31
        self.assertTrue(breaker.allow("x"))
        breaker.success("x")
        self.assertEqual(breaker.status("x")["failures"],0)
    def test_no_feed_is_truthful(self):
        self.assertFalse(readiness()["automatic_live_failover_enabled"])
        self.assertFalse(readiness()["quote_available"])
        self.assertEqual(ReadOnlyRouter([]).quote("RELIANCE")["status"],"UNAVAILABLE")
    def test_invalid_input(self):
        for symbol in ("","../secret","reliance"):
            with self.assertRaises(ValueError): ReadOnlyRouter([]).quote(symbol)
        with self.assertRaises(ValueError): ReadOnlyRouter([]).quote("RELIANCE",0)
if __name__=="__main__":unittest.main()
