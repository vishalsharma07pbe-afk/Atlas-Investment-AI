import unittest
from app.instrument_resolution import resolve_upstox_instrument,make_subscription

class InstrumentResolutionTests(unittest.TestCase):
    def setUp(self):
        self.record={"exchange":"NSE","symbol":"RELIANCE","isin":"INE002A01018",
                     "active":True,"listing_status":"ACTIVE"}
    def test_nse_isin_resolves(self):
        result=resolve_upstox_instrument(self.record)
        self.assertTrue(result["subscription_ready"])
        self.assertEqual(result["instrument_key"],"NSE_EQ|INE002A01018")
        self.assertEqual(make_subscription(self.record,"request-1")["data"]["instrumentKeys"],["NSE_EQ|INE002A01018"])
    def test_never_guess_bse_key(self):
        self.record["exchange"]="BSE"
        result=resolve_upstox_instrument(self.record)
        self.assertFalse(result["subscription_ready"])
        self.assertIsNone(result["instrument_key"])
    def test_never_resolve_inactive_or_missing_isin(self):
        self.record["active"]=False
        self.assertFalse(resolve_upstox_instrument(self.record)["subscription_ready"])
        self.record["active"]=True
        self.record["isin"]=None
        self.assertFalse(resolve_upstox_instrument(self.record)["subscription_ready"])
        with self.assertRaises(ValueError):make_subscription(self.record,"request-1")

if __name__=="__main__":unittest.main()
