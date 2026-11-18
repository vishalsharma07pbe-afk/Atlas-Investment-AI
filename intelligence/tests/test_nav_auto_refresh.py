import gzip
import json
import tempfile
import unittest
from unittest.mock import patch

from app import nav_auto_refresh, nav_catalog

SAMPLE = [
    {"instrument_key":"INF846K016M6","name":"Axis Long Duration Fund Direct Growth",
     "last_price":12.3456,"last_price_date":"2026-11-14","amc":"AXIS","scheme_type":"DEBT",
     "plan":"DIRECT","purchase_allowed":True,"redemption_allowed":True,
     "minimum_purchase_amount":500,"settlement_type":"T1"},
    {"instrument_key":"INVALID","name":"Rejected fund","last_price":10,
     "last_price_date":"2026-11-14"},
]

class Response:
    def __init__(self,content): self.content=content
    def raise_for_status(self): return None

class Client:
    def __init__(self,content): self.content=content;self.calls=[]
    def get(self,url): self.calls.append(url);return Response(self.content)

class NavAutoRefreshTests(unittest.TestCase):
    def test_parse_validates_and_deduplicates(self):
        rows,invalid=nav_auto_refresh.parse_snapshot(gzip.compress(json.dumps(SAMPLE).encode()))
        self.assertEqual(len(rows),1)
        self.assertEqual(invalid,1)
        self.assertEqual(rows[0]["provider_key"],"INF846K016M6")
        self.assertEqual(rows[0]["nav"],"12.3456")
        self.assertEqual(rows[0]["nav_date_status"],"DECLARED")

    def test_missing_provider_nav_date_is_not_misrepresented(self):
        sample=[{**SAMPLE[0],"last_price_date":None}]
        rows,invalid=nav_auto_refresh.parse_snapshot(
            gzip.compress(json.dumps(sample).encode()),nav_auto_refresh.date(2026,11,16))
        self.assertEqual(invalid,0)
        self.assertEqual(rows[0]["nav_date"],"2026-11-16")
        self.assertEqual(rows[0]["nav_date_status"],"PROVIDER_NOT_SUPPLIED")

    def test_refresh_is_idempotent_and_searchable(self):
        payload=gzip.compress(json.dumps(SAMPLE).encode())
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(nav_catalog,"DB_PATH",nav_catalog.Path(folder)/"nav.sqlite3"):
            first=nav_auto_refresh.refresh_once(Client(payload))
            second=nav_auto_refresh.refresh_once(Client(payload))
            self.assertEqual(first["inserted_history_rows"],1)
            self.assertEqual(second["inserted_history_rows"],0)
            found=nav_catalog.search_schemes("Axis")
            self.assertEqual(found["items"][0]["scheme_code"],"INF846K016M6")
            self.assertEqual(nav_catalog.catalog_status()["last_refresh_status"],"SUCCESS")
            details=nav_catalog.fund_details("INF846K016M6")
            self.assertEqual(details["scheme_type"],"DEBT")
            self.assertEqual(details["trading_terms"]["minimum_purchase_amount"],500)
            self.assertEqual(details["recommendation"]["status"],"BLOCKED_INSUFFICIENT_VERIFIED_FACTORS")
            self.assertIsNone(details["portfolio"]["top_holdings"])

    def test_invalid_payload_fails_closed_and_is_audited(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(nav_catalog,"DB_PATH",nav_catalog.Path(folder)/"nav.sqlite3"):
            with self.assertRaisesRegex(RuntimeError,"MF_SNAPSHOT_INVALID_JSON"):
                nav_auto_refresh.refresh_once(Client(b"not-json"))
            status=nav_catalog.catalog_status()
            self.assertEqual(status["scheme_count"],0)
            self.assertEqual(status["last_refresh_status"],"FAILED")

    def test_schedule_configuration_requires_no_account(self):
        cfg=nav_auto_refresh.config({"ATLAS_MF_NAV_AUTO_REFRESH_ENABLED":"true"})
        self.assertTrue(cfg["enabled"])
        self.assertFalse(cfg["requires_upstox_account"])
        self.assertEqual(cfg["schedule"],"06:30 Asia/Kolkata")

if __name__ == "__main__": unittest.main()
