import json,tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from pydantic import ValidationError
from app.notification_feed_sync import FeedConfig,Registry,sync_directory

NOW=datetime.now(timezone.utc)-timedelta(minutes=2)
def feed(enabled=True,rights=True):
    return {"source_name":"Authorized publisher","source_url":"https://example.org/ipo",
        "enabled":enabled,"collection_authorized":rights,"redistribution_authorized":rights}
def snapshot():
    published=NOW.isoformat()
    return {"source_name":"Authorized publisher","source_url":"https://example.org/ipo",
        "retrieved_at":(NOW+timedelta(minutes=1)).isoformat(),
        "collection_authorized":True,"redistribution_authorized":True,
        "alerts":[{"id":"ipo-example","category":"IPO_SUBSCRIPTION",
            "title":"Illustrative subscription","description":"Test only",
            "published_at":published,"source_name":"Authorized publisher",
            "source_url":"https://example.org/ipo","subscription_total_x":"1.8",
            "subscription_as_of":published}]}
class FeedSyncTests(unittest.TestCase):
    def test_disabled_and_rights_are_fail_closed(self):
        with self.assertRaises(ValidationError):FeedConfig.model_validate(feed(rights=False))
        with self.assertRaises(ValidationError):Registry.model_validate({"feeds":[feed(),feed()]})

    def test_dry_run_apply_and_repeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);inbox=root/"inbox";inbox.mkdir()
            registry=root/"registry.json";registry.write_text(json.dumps({"feeds":[feed()]}))
            (inbox/"sample.json").write_text(json.dumps(snapshot()))
            out=root/"alerts.json"
            first=sync_directory(registry,inbox,out)
            self.assertEqual(first["results"][0]["added"],1)
            self.assertFalse(out.exists())
            second=sync_directory(registry,inbox,out,apply=True)
            self.assertEqual(second["results"][0]["status"],"IMPORTED")
            self.assertEqual(len(json.loads(out.read_text())),1)
            repeat=sync_directory(registry,inbox,out,apply=True)
            self.assertEqual(repeat["results"][0]["skipped_older_or_equal"],1)

    def test_unapproved_source_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);inbox=root/"inbox";inbox.mkdir()
            registry=root/"registry.json";registry.write_text(json.dumps({"feeds":[feed(enabled=False)]}))
            (inbox/"sample.json").write_text(json.dumps(snapshot()))
            out=root/"alerts.json"
            result=sync_directory(registry,inbox,out,apply=True)
            self.assertEqual(result["results"][0]["reason"],"SOURCE_NOT_ENABLED")
            self.assertFalse(out.exists())

    def test_symlinks_are_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);inbox=root/"inbox";inbox.mkdir()
            outside=root/"outside.json";outside.write_text(json.dumps(snapshot()))
            (inbox/"link.json").symlink_to(outside)
            registry=root/"registry.json";registry.write_text(json.dumps({"feeds":[feed()]}))
            self.assertEqual(sync_directory(registry,inbox,root/"alerts.json")["scanned"],0)
if __name__=="__main__":unittest.main()
