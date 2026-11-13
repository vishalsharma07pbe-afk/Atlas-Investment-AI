import json,os,tempfile,unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from app.notifications import summary,details

def alert():
    t=(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat()
    return {"id":"ipo-test-1","category":"IPO_SUBSCRIPTION","title":"Example subscription snapshot",
        "description":"Test data, not an actual IPO","published_at":t,"event_date":"2026-11-14",
        "source_name":"Example Source","source_url":"https://example.org/ipo",
        "subscription_total_x":"2.35","subscription_as_of":t}

class NotificationTests(unittest.TestCase):
    def test_summary_only_returns_ids_and_details_are_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=os.path.join(tmp,"alerts.json")
            with open(path,"w") as f:json.dump([alert()],f)
            with patch.dict(os.environ,{"ATLAS_ALERTS_FILE":path}):
                badge=summary()
                self.assertEqual(badge["ids"],["ipo-test-1"])
                self.assertNotIn("alerts",badge)
                feed=details()
                self.assertEqual(feed["alerts"][0]["subscription_total_x"],"2.35")
                self.assertFalse(feed["live_feed_connected"])

    def test_empty_source_does_not_invent_ipo_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ,{"ATLAS_ALERTS_FILE":os.path.join(tmp,"missing.json")}):
                self.assertEqual(summary()["total"],0)
                self.assertEqual(details()["alerts"],[])

    def test_duplicate_ids_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=os.path.join(tmp,"alerts.json")
            with open(path,"w") as f:json.dump([alert(),alert()],f)
            with patch.dict(os.environ,{"ATLAS_ALERTS_FILE":path}):
                with self.assertRaises(RuntimeError):summary()

    def test_subscription_requires_timestamp_and_ratio(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=os.path.join(tmp,"alerts.json")
            item=alert()
            item.pop("subscription_as_of")
            with open(path,"w") as f:json.dump([item],f)
            with patch.dict(os.environ,{"ATLAS_ALERTS_FILE":path}):
                with self.assertRaises(RuntimeError):details()

if __name__=="__main__":unittest.main()
