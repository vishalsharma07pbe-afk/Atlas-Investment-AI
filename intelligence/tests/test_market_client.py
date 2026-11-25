import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app import market_client


class _Response:
    def __init__(self, payload):
        self.payload=json.dumps(payload).encode()
    def __enter__(self):
        return self
    def __exit__(self,*_args):
        return False
    def read(self,_limit):
        return self.payload


class MarketClientTest(unittest.TestCase):
    def test_rewrites_to_protected_read_only_route(self):
        captured={}
        def open_request(request,timeout):
            captured["url"]=request.full_url
            captured["token"]=request.get_header("X-atlas-service-token")
            captured["timeout"]=timeout
            return _Response({"count":21})
        with patch.dict("os.environ",{"INTERNAL_SERVICE_TOKEN":"service-secret"}), \
             patch.object(market_client,"settings",SimpleNamespace(backend_url="http://backend")), \
             patch.object(market_client,"urlopen",side_effect=open_request):
            result=market_client.backend_json("/api/v1/market-data/instruments/7/candles?limit=250")
        self.assertEqual(result,{"count":21})
        self.assertEqual(captured["url"],"http://backend/api/v1/internal/feed/instruments/7/candles?limit=250")
        self.assertEqual(captured["token"],"service-secret")
        self.assertEqual(captured["timeout"],10)

    def test_calendar_context_uses_only_fixed_internal_read_route(self):
        self.assertEqual(market_client._internal_path("/api/v1/market-data/session-context"),
                         "/api/v1/internal/feed/session-context")
        with self.assertRaises(HTTPException):
            market_client._internal_path("/api/v1/market-data/session-context?exchange=OTHER")

    def test_rejects_unapproved_backend_route(self):
        with patch.dict("os.environ",{"INTERNAL_SERVICE_TOKEN":"service-secret"}):
            with self.assertRaises(HTTPException) as raised:
                market_client.backend_json("/api/v1/portfolio")
        self.assertEqual(raised.exception.status_code,500)

    def test_requires_internal_service_credential(self):
        with patch.dict("os.environ",{},clear=True):
            with self.assertRaises(HTTPException) as raised:
                market_client.backend_json("/api/v1/instruments?limit=20")
        self.assertEqual(raised.exception.status_code,503)


if __name__ == "__main__":
    unittest.main()
