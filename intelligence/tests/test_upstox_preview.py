import json
import unittest
from datetime import date
from unittest.mock import patch
from fastapi import HTTPException
from app import upstox_preview as preview

class FakeResponse:
    status=200
    def __init__(self,data):self.data=data
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,size):return self.data

class FakeOpener:
    def __init__(self,data):self.data=data;self.requests=[]
    def open(self,request,timeout):
        self.requests.append(request)
        return FakeResponse(self.data)

class ProviderPreviewTests(unittest.TestCase):
    def test_defaults_block_without_network(self):
        with patch.object(preview.settings,"provider","MANUAL_CSV"):
            with patch.object(preview,"build_opener") as opener:
                with self.assertRaises(HTTPException) as exc:
                    preview.preview_daily("NSE_EQ|INE848E01016",date(2026,1,1),date(2026,1,2))
                self.assertEqual(exc.exception.status_code,403)
                opener.assert_not_called()

    def test_valid_payload_is_unverified_and_not_persisted(self):
        data=json.dumps({"status":"success","data":{"candles":[
            ["2026-01-02T00:00:00+05:30",100,105,99,103,1200,0]
        ]}}).encode()
        opener=FakeOpener(data)
        with patch.object(preview.settings,"provider","UPSTOX"),patch.object(preview.settings,"licensed_data_access",True),patch.object(preview.settings,"entitlement_confirmed",True),patch.object(preview.settings,"upstox_token","test-secret"),patch.object(preview,"build_opener",return_value=opener):
            result=preview.preview_daily("NSE_EQ|INE848E01016",date(2026,1,1),date(2026,1,2))
        self.assertEqual(result["status"],"PREVIEW_ONLY")
        self.assertEqual(result["candles"][0]["adjustment_status"],"UNVERIFIED")
        self.assertEqual(len(opener.requests),1)
        self.assertIn("api.upstox.com/v3/historical-candle/",opener.requests[0].full_url)
        self.assertNotIn("test-secret",str(result))

    def test_invalid_key_rejected_before_network(self):
        with patch.object(preview.settings,"provider","UPSTOX"),patch.object(preview.settings,"licensed_data_access",True),patch.object(preview.settings,"entitlement_confirmed",True),patch.object(preview.settings,"upstox_token","secret"),patch.object(preview,"build_opener") as opener:
            with self.assertRaises(HTTPException) as exc:
                preview.preview_daily("https://attacker.invalid/",date(2026,1,1),date(2026,1,2))
            self.assertEqual(exc.exception.status_code,422)
            opener.assert_not_called()

    def test_invalid_prices_fail_closed(self):
        data=json.dumps({"status":"success","data":{"candles":[
            ["2026-01-02T00:00:00+05:30",100,90,99,103,1200,0]
        ]}}).encode()
        with patch.object(preview.settings,"provider","UPSTOX"),patch.object(preview.settings,"licensed_data_access",True),patch.object(preview.settings,"entitlement_confirmed",True),patch.object(preview.settings,"upstox_token","secret"),patch.object(preview,"build_opener",return_value=FakeOpener(data)):
            with self.assertRaises(HTTPException) as exc:
                preview.preview_daily("NSE_EQ|INE848E01016",date(2026,1,1),date(2026,1,2))
            self.assertEqual(exc.exception.status_code,502)

if __name__=="__main__":
    unittest.main()
