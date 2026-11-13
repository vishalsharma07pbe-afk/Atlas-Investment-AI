import json,tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
from app.notification_source_health import inspect_sources

class SourceHealthTests(unittest.TestCase):
    def test_missing_registry_is_explicitly_unconfigured(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=inspect_sources(Path(tmp)/"missing.json")
            self.assertEqual(result["status"],"NOT_CONFIGURED")
            self.assertFalse(result["live_feed_connected"])

    def test_source_health_and_stale_subscription(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            registry=root/"feeds.json";alerts=root/"alerts.json"
            registry.write_text(json.dumps({"feeds":[{"source_name":"Sample publisher",
                "source_url":"https://example.org/ipo","enabled":True,
                "collection_authorized":True,"redistribution_authorized":True}]}))
            at=(datetime.now(timezone.utc)-timedelta(days=3)).isoformat()
            alerts.write_text(json.dumps([{"id":"ipo-sample","category":"IPO_SUBSCRIPTION",
                "title":"Sample subscription","description":"Not live",
                "published_at":at,"source_name":"Sample publisher",
                "source_url":"https://example.org/ipo","subscription_total_x":"2.0",
                "subscription_as_of":at}]))
            with patch.dict("os.environ",{"ATLAS_ALERTS_FILE":str(alerts)}):
                result=inspect_sources(registry)
            source=result["sources"][0]
            self.assertEqual(source["status"],"SUBSCRIPTION_STALE")
            self.assertEqual(source["alert_count"],1)
            self.assertTrue(source["subscription_snapshot_stale"])
            self.assertFalse(result["live_feed_connected"])

    def test_configured_but_no_imported_alerts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);registry=root/"feeds.json";alerts=root/"alerts.json"
            registry.write_text(json.dumps({"feeds":[{"source_name":"Sample publisher",
                "source_url":"https://example.org/ipo","enabled":True,
                "collection_authorized":True,"redistribution_authorized":True}]}))
            alerts.write_text("[]")
            with patch.dict("os.environ",{"ATLAS_ALERTS_FILE":str(alerts)}):
                result=inspect_sources(registry)
            self.assertEqual(result["sources"][0]["status"],"NO_ALERTS_IMPORTED")
if __name__=="__main__":unittest.main()
