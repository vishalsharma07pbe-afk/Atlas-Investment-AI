import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import ohlcv_store as store

class OhlcvStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.override = patch.object(store,"DB_PATH",Path(self.temp.name)/"ohlcv.sqlite3")
        self.override.start()
    def tearDown(self):
        self.override.stop()
        self.temp.cleanup()
    def test_dedup_and_provenance(self):
        candle={"date":"2026-11-10","open":"100","high":"110","low":"90","close":"105","volume":1000}
        self.assertEqual(store.import_candles("RELIANCE","NSE","UPSTOX",[candle])["inserted"],1)
        self.assertEqual(store.import_candles("RELIANCE","NSE","UPSTOX",[candle])["unchanged"],1)
        self.assertEqual(len(store.history("RELIANCE","NSE")["items"]),1)
        self.assertEqual(store.history("RELIANCE","NSE")["items"][0]["source"],"UPSTOX")
        with self.assertRaisesRegex(ValueError,"CONFLICTING_SOURCE_OBSERVATION"):
            store.import_candles("RELIANCE","NSE","UPSTOX",[{**candle,"close":"106"}])
        self.assertEqual(store.import_candles("RELIANCE","NSE","OTHER",[candle])["inserted"],1)
    def test_validation(self):
        candle={"date":"2026-11-10","open":"100","high":"95","low":"90","close":"105","volume":1000}
        with self.assertRaisesRegex(ValueError,"INCONSISTENT_OHLC"):
            store.import_candles("ABC","NSE","UPSTOX",[candle])
        with self.assertRaises(ValueError):
            store.import_candles("ABC","NSE","UPSTOX",[{**candle,"high":"110","volume":-1}])
        with self.assertRaises(ValueError):
            store.import_candles("ABC","NSE","UPSTOX",[{**candle,"high":"110"}]*2)
if __name__ == "__main__":
    unittest.main()
