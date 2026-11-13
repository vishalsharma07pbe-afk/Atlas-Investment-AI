import unittest
from app.upstox_feed_selection import parse_ids,resolve_ids,FeedSelectionError

def record(id):
    return {"exchange":"NSE","symbol":"TEST","isin":"INE002A01018",
            "active":True,"listing_status":"ACTIVE"}

class SelectionTests(unittest.TestCase):
    def test_ids(self):
        self.assertEqual(parse_ids(" 1, 2 "),[1,2])
        self.assertEqual(parse_ids(""),[])
        for value in ("1,1","0","-2","abc","1,","1;2"):
            with self.assertRaises(FeedSelectionError):parse_ids(value)
    def test_resolves_from_registry(self):
        self.assertEqual(resolve_ids([1],lambda path:record(1)),["NSE_EQ|INE002A01018"])
    def test_duplicate_keys_blocked(self):
        with self.assertRaises(FeedSelectionError):
            resolve_ids([1,2],lambda path:record(1))
    def test_inactive_blocked(self):
        def fetch(path):
            result=record(1);result["active"]=False;return result
        with self.assertRaises(FeedSelectionError):resolve_ids([1],fetch)
    def test_backend_errors_are_safe(self):
        def fetch(path):raise RuntimeError("private backend message")
        with self.assertRaisesRegex(FeedSelectionError,"Instrument registry unavailable"):
            resolve_ids([1],fetch)

if __name__=="__main__":unittest.main()
