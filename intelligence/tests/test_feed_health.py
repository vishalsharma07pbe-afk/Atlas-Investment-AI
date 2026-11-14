import unittest
from datetime import datetime, timezone
from app.feed_health import assess_feed

NOW=datetime(2026,11,14,tzinfo=timezone.utc)

class FeedHealthTests(unittest.TestCase):
    def base(self, **kwargs):
        value=dict(configuration_status="CONFIGURED",blockers=[],worker_running=True,
                   transport_connected=True,frames_processed=10,rejected_entries=0,
                   cached_instruments=3)
        value.update(kwargs)
        return assess_feed(value, NOW)

    def test_connected_is_not_verified_live(self):
        result=self.base()
        self.assertEqual(result["state"],"CONNECTED_UNVERIFIED")
        self.assertFalse(result["live_prices_verified"])
        self.assertFalse(result["entitlement_verified"])
        self.assertFalse(result["automatic_collection_authorized_by_this_check"])

    def test_blocked_even_if_transport_connected(self):
        result=self.base(configuration_status="NOT_READY",blockers=["MISSING_ACCESS_TOKEN"])
        self.assertEqual(result["state"],"BLOCKED")
        self.assertIn("MISSING_ACCESS_TOKEN",result["blocker_codes"])

    def test_stopped_disconnected_and_empty(self):
        self.assertEqual(self.base(worker_running=False)["state"],"STOPPED")
        self.assertEqual(self.base(transport_connected=False)["state"],"DISCONNECTED")
        self.assertEqual(self.base(frames_processed=0)["state"],"NO_DATA")

    def test_degraded_rejections(self):
        self.assertEqual(self.base(frames_processed=3,rejected_entries=3)["state"],"DEGRADED")

    def test_invalid_counters_do_not_raise(self):
        result=self.base(frames_processed=-1,rejected_entries=-4,cached_instruments="bad")
        self.assertEqual(result["frames_processed"],0)
        self.assertEqual(result["cached_instruments"],0)
        self.assertEqual(result["state"],"NO_DATA")

if __name__=="__main__":
    unittest.main()
