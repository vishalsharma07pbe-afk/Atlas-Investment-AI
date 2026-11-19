import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import dynamic_feed_selection as module


class FakeSupervisor:
    def __init__(self):
        self.worker = SimpleNamespace(active_keys=set())
        self.selected_count = 0
        self.startup_result = {}
        self.starts = []

    async def stop(self):
        self.worker.active_keys.clear()

    async def start(self, **kwargs):
        keys = set(kwargs["keys"])
        self.starts.append(keys)
        self.worker.active_keys = keys
        self.selected_count = len(keys)
        return {"status": "STARTING"}


class DynamicLiveSelectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_ui_subscription_is_added_and_removed_without_losing_indices(self):
        supervisor = FakeSupervisor()
        settings = SimpleNamespace(
            provider="UPSTOX",
            upstox_token="redacted-test-token",
            licensed_data_access=True,
            entitlement_confirmed=True,
            backend_url="http://backend:8080",
        )
        selection = {
            "holding_symbol_count": 0,
            "subscriptions": [],
            "missing_symbols": [],
        }
        old_keys = os.environ.pop("ATLAS_UPSTOX_INSTRUMENT_KEYS", None)
        old_ids = os.environ.pop("ATLAS_UPSTOX_INSTRUMENT_IDS", None)
        old_enabled = os.environ.get("ATLAS_UPSTOX_FEED_ENABLED")
        os.environ["ATLAS_UPSTOX_FEED_ENABLED"] = "true"
        try:
            with patch.object(module, "settings", settings), patch.object(
                module, "feed_supervisor", supervisor
            ):
                selector = module.DynamicFeedSelection()
                selector._fetch = lambda: selection
                await selector.subscribe("NSE_EQ|INE002A01018")
                self.assertEqual(
                    supervisor.worker.active_keys,
                    module.INDEX_KEYS | {"NSE_EQ|INE002A01018"},
                )
                await selector.unsubscribe("NSE_EQ|INE002A01018")
                self.assertEqual(supervisor.worker.active_keys, module.INDEX_KEYS)
        finally:
            if old_keys is not None:
                os.environ["ATLAS_UPSTOX_INSTRUMENT_KEYS"] = old_keys
            if old_ids is not None:
                os.environ["ATLAS_UPSTOX_INSTRUMENT_IDS"] = old_ids
            if old_enabled is None:
                os.environ.pop("ATLAS_UPSTOX_FEED_ENABLED", None)
            else:
                os.environ["ATLAS_UPSTOX_FEED_ENABLED"] = old_enabled


if __name__ == "__main__":
    unittest.main()
