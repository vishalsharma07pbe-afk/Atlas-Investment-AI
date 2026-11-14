import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import upstox_history as history
from app import ohlcv_store

class HistoricalFetchTests(unittest.TestCase):
    def test_fail_closed(self):
        with patch.dict("os.environ",{"ATLAS_UPSTOX_HISTORICAL_AUTHORIZED":"false"},clear=False):
            self.assertEqual(history.import_upstox_daily("RELIANCE","NSE","2026-11-01","2026-11-02")["status"],
                             "BLOCKED_AUTHORIZATION")
    def test_schema_rejects_bad_rows(self):
        with self.assertRaises(history.ProviderFailure):
            history.parse_upstox_candles({"status":"success","data":{"candles":[["bad"]]}})
    def test_authorized_import_and_dedup(self):
        body={"status":"success","data":{"candles":[["2026-11-10T15:30:00+05:30",100,110,90,105,1000,0]]}}
        env={"ATLAS_UPSTOX_HISTORICAL_AUTHORIZED":"true",
             "MARKET_DATA_USAGE_RIGHTS_CONFIRMED":"true",
             "MARKET_DATA_ENTITLEMENT_CONFIRMED":"true",
             "UPSTOX_ACCESS_TOKEN":"test",
             "ATLAS_UPSTOX_SYMBOL_MAP":'{"RELIANCE":"NSE_EQ|INE002A01018"}'}
        with tempfile.TemporaryDirectory() as tmp,patch.object(ohlcv_store,"DB_PATH",Path(tmp)/"ohlcv.sqlite3"),patch.dict("os.environ",env,clear=False),patch.object(history,"_request",return_value=body) as fetch:
            result=history.import_upstox_daily("RELIANCE","NSE","2026-11-01","2026-11-12")
            self.assertEqual(result["inserted"],1)
            self.assertEqual(history.import_upstox_daily("RELIANCE","NSE","2026-11-01","2026-11-12")["unchanged"],1)
            self.assertIn("/v3/historical-candle/NSE_EQ%7CINE002A01018/days/1/",fetch.call_args.args[0])
    def test_reject_outside_range(self):
        body={"status":"success","data":{"candles":[["2026-10-01T15:30:00+05:30",100,110,90,105,1000]]}}
        env={"ATLAS_UPSTOX_HISTORICAL_AUTHORIZED":"true","MARKET_DATA_USAGE_RIGHTS_CONFIRMED":"true",
             "MARKET_DATA_ENTITLEMENT_CONFIRMED":"true","UPSTOX_ACCESS_TOKEN":"test",
             "ATLAS_UPSTOX_SYMBOL_MAP":'{"RELIANCE":"NSE_EQ|INE002A01018"}'}
        with patch.dict("os.environ",env,clear=False),patch.object(history,"_request",return_value=body):
            with self.assertRaisesRegex(history.ProviderFailure,"CANDLE_OUTSIDE_REQUESTED_RANGE"):
                history.import_upstox_daily("RELIANCE","NSE","2026-11-01","2026-11-12")
if __name__=="__main__":
    unittest.main()
