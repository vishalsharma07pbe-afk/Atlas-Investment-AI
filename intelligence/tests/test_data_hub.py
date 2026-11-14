import unittest
from unittest.mock import patch
from app import data_hub

class HubTests(unittest.TestCase):
    def test_remote_never_claims_live(self):
        status=data_hub.health()
        self.assertFalse(status["live_feed_verified"])
        self.assertFalse(status["automatic_failover_enabled"])
        self.assertFalse(data_hub.lookup("RELIANCE","EQUITY")["live"])
        self.assertEqual(data_hub.lookup("RELIANCE","EQUITY")["items"],[])
    def test_local_nav_provenance(self):
        with patch.object(data_hub.nav_catalog,"search_schemes",return_value={"items":[{"scheme_code":123,"nav":"42.3","nav_date":"2020-01-01","source":"AMFI_MANUAL_DOWNLOAD"}]}):
            result=data_hub.lookup("Example","MUTUAL_FUND")
        self.assertEqual(result["items"][0]["source"],"AMFI_MANUAL_DOWNLOAD")
        self.assertEqual(result["items"][0]["freshness"],"STALE")
        self.assertFalse(result["items"][0]["live"])
    def test_invalid_search(self):
        for query in ("", "x"*101):
            with self.assertRaises(ValueError): data_hub.lookup(query,"EQUITY")
        with self.assertRaises(ValueError): data_hub.lookup("test","CRYPTO")
if __name__=="__main__": unittest.main()
