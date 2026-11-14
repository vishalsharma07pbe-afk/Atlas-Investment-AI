import asyncio
import unittest
from unittest.mock import patch
from app import reliability_monitor as module

class MonitorTests(unittest.TestCase):
    def test_disabled_by_default_and_invalid_cadence(self):
        cfg = module.config({})
        self.assertFalse(cfg["enabled"])
        self.assertEqual(cfg["interval_seconds"], 900)
        self.assertEqual(module.config({"ATLAS_READINESS_MONITOR_ENABLED":"true",
                                        "ATLAS_READINESS_MONITOR_INTERVAL_SECONDS":"0"})["blocker"],
                         "INVALID_MONITOR_INTERVAL")
        self.assertEqual(module.config({"ATLAS_READINESS_MONITOR_ENABLED":"true",
                                        "ATLAS_READINESS_MONITOR_INTERVAL_SECONDS":"not-a-number"})["blocker"],
                         "INVALID_MONITOR_INTERVAL")

    def test_snapshot_uses_server_computed_issues(self):
        with patch.object(module, "readiness", return_value={
            "generated_at":"2026-11-14T00:00:00+00:00",
            "datasets":[{"code":"GLOBAL_NEWS","status":"STALE_DATA"},
                        {"code":"MUTUAL_FUND_NAV","status":"RECENT_LOCAL_EVIDENCE"}]}), \
             patch.object(module, "record_snapshot", return_value={"observed_issues":2}) as record:
            result = module.observe_once()
        self.assertEqual(result["observed_issues"], 2)
        record.assert_called_once_with([
            {"dataset":"GLOBAL_NEWS","code":"STALE"},
            {"dataset":"MARKET_DATA","code":"UNVERIFIED_SOURCE"}])

    def test_start_stop_and_safe_status(self):
        async def run():
            monitor = module.Monitor()
            with patch.object(module, "config", return_value={
                "enabled":True,"interval_seconds":60,"blocker":None}), \
                 patch.object(module, "observe_once", return_value={"observed_issues":1}):
                await monitor.start()
                await asyncio.sleep(0.02)
                self.assertTrue(monitor.status()["running"])
                self.assertGreaterEqual(monitor.runs, 1)
                await monitor.stop()
                self.assertFalse(monitor.status()["running"])
                self.assertFalse(monitor.status()["live_feed_connected"])
        asyncio.run(run())

    def test_monitor_failures_do_not_leak_exceptions(self):
        async def run():
            monitor = module.Monitor()
            with patch.object(module, "config", return_value={
                "enabled":True,"interval_seconds":60,"blocker":None}), \
                 patch.object(module, "observe_once", side_effect=RuntimeError("secret-token")):
                await monitor.start()
                await asyncio.sleep(0.02)
                status = monitor.status()
                self.assertEqual(status["last_error_code"], "LOCAL_READINESS_OBSERVATION_FAILED")
                self.assertNotIn("secret-token", str(status))
                await monitor.stop()
        asyncio.run(run())

if __name__ == "__main__":
    unittest.main()
