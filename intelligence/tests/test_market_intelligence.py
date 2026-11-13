import unittest
from datetime import date,timedelta
from app.market_intelligence import analyze_market

TODAY=date(2026,11,13)
def fixture(count=60,change=0,adjustment="RAW_UNADJUSTED"):
    start=TODAY-timedelta(days=count-1)
    candles=[]
    for i in range(count):
        price=100+i*.3
        if i==count-1:price+=change
        candles.append({"trade_date":(start+timedelta(days=i)).isoformat(),
            "open":price,"high":price+2,"low":price-2,"close":price+.5,
            "volume":5000 if i==count-1 else 1000,
            "adjustment_status":adjustment})
    return {"candles":candles}

class MarketIntelligenceTests(unittest.TestCase):
    def test_integrated_rankings_and_breadth(self):
        instruments=[{"id":1,"symbol":"AAA","exchange":"NSE"},
                     {"id":2,"symbol":"BBB","exchange":"NSE"}]
        data={1:fixture(change=8),2:fixture(change=-8)}
        result=analyze_market(instruments,lambda i:data[i],as_of=TODAY)
        self.assertEqual(result["eligible_count"],2)
        self.assertEqual(result["breadth"]["advancing"],1)
        self.assertEqual(result["breadth"]["declining"],1)
        self.assertEqual(result["top_gainers"][0]["symbol"],"AAA")
        self.assertEqual(result["top_losers"][0]["symbol"],"BBB")
        self.assertEqual(result["volume_leaders"][0]["relative_volume_20"],5)
        self.assertIn("UNUSUAL_VOLUME_2X",result["anomaly_watch"][0]["flags"])

    def test_invalid_or_unverified_adjustments_are_excluded(self):
        data=fixture(adjustment="UNVERIFIED")
        result=analyze_market([{"id":1,"symbol":"X","exchange":"NSE"}],
                              lambda i:data,as_of=TODAY)
        self.assertEqual(result["eligible_count"],0)
        self.assertEqual(result["skipped"]["MIXED_OR_UNVERIFIED_ADJUSTMENT"],1)

    def test_stale_short_and_failed_backend(self):
        instruments=[{"id":i,"symbol":str(i),"exchange":"NSE"} for i in range(3)]
        stale=fixture()
        for c in stale["candles"]:
            c["trade_date"]=(date.fromisoformat(c["trade_date"])-timedelta(days=30)).isoformat()
        def load(i):
            if i==0:return fixture(10)
            if i==1:return stale
            raise ConnectionError("offline")
        result=analyze_market(instruments,load,as_of=TODAY)
        self.assertEqual(result["eligible_count"],0)
        self.assertEqual(result["skipped"]["INSUFFICIENT_HISTORY"],1)
        self.assertEqual(result["skipped"]["STALE_OR_FUTURE"],1)
        self.assertEqual(result["skipped"]["BACKEND_UNAVAILABLE"],1)

    def test_universe_is_bounded(self):
        instruments=[{"id":i,"symbol":str(i),"exchange":"NSE"} for i in range(25)]
        calls=[]
        def load(i):
            calls.append(i)
            return fixture()
        result=analyze_market(instruments,load,as_of=TODAY)
        self.assertEqual(result["universe_size"],20)
        self.assertEqual(len(calls),20)

if __name__=="__main__":
    unittest.main()
