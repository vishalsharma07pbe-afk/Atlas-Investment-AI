import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app import market_indices


class MarketIndexTests(unittest.TestCase):
    configured = SimpleNamespace(
        provider="UPSTOX", licensed_data_access=True,
        entitlement_confirmed=True, upstox_token="test-only-token"
    )

    def test_fails_closed_when_provider_rejects_access(self):
        with patch.object(market_indices, "settings", self.configured), patch.object(
                market_indices, "_request", side_effect=market_indices.ProviderFailure("PROVIDER_ACCESS_REJECTED")):
            result = market_indices.snapshots()
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["reason"], "PROVIDER_ACCESS_REJECTED")
        self.assertEqual(result["items"], [])

    def test_normalizes_authorized_index_snapshot(self):
        timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
        payload = {"status": "success", "data": {
            "NSE_INDEX:Nifty 50": {
                "instrument_token": "NSE_INDEX|Nifty 50",
                "last_price": 25050,
                "prev_close_price": 25000,
                "net_change": 50,
                "last_trade_time": str(timestamp),
            }
        }}
        with patch.object(market_indices, "settings", self.configured), patch.object(
                market_indices, "_request", return_value=payload):
            result = market_indices.snapshots()
        self.assertEqual(result["status"], "AVAILABLE")
        self.assertEqual(result["items"][0]["label"], "NIFTY 50")
        self.assertEqual(result["items"][0]["change_percent"], 0.2)
        self.assertEqual(result["items"][0]["freshness"], "LIVE")

    def test_future_timestamp_is_not_a_live_quote(self):
        timestamp = int((datetime.now(timezone.utc)+timedelta(minutes=10)).timestamp()*1000)
        payload = {"status":"success","data":{"nifty":{
            "instrument_token":"NSE_INDEX|Nifty 50","last_price":25050,
            "prev_close_price":25000,"net_change":50,"last_trade_time":str(timestamp)}}}
        with patch.object(market_indices,"settings",self.configured), patch.object(market_indices,"_request",return_value=payload):
            result=market_indices.snapshots()
        self.assertEqual(result["status"],"UNAVAILABLE")
        self.assertEqual(result["items"],[])

if __name__ == "__main__":
    unittest.main()
