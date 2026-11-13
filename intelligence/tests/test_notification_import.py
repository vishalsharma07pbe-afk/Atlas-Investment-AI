import json,tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from pydantic import ValidationError
from app.notification_import import import_snapshot,Snapshot

NOW=datetime.now(timezone.utc)-timedelta(minutes=2)
def alert(identifier="ipo-a",offset=0):
    at=(NOW+timedelta(seconds=offset)).isoformat()
    return {"id":identifier,"category":"IPO_SUBSCRIPTION","title":"Illustrative IPO snapshot",
        "description":"Sample test alert","event_date":"2026-11-20","published_at":at,
        "source_name":"Operator source","source_url":"https://example.org/ipo",
        "subscription_total_x":"3.4","subscription_as_of":at}
def snapshot(items,allowed=True):
    return {"source_name":"Operator source","source_url":"https://example.org/ipo",
        "retrieved_at":(NOW+timedelta(minutes=1)).isoformat(),
        "collection_authorized":allowed,"redistribution_authorized":allowed,"alerts":items}

class ImportTests(unittest.TestCase):
    def test_dry_run_does_not_write_and_apply_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            src=Path(folder)/"snapshot.json";out=Path(folder)/"feed.json"
            src.write_text(json.dumps(snapshot([alert()])))
            self.assertEqual(import_snapshot(src,out)["status"],"DRY_RUN")
            self.assertFalse(out.exists())
            self.assertEqual(import_snapshot(src,out,dry_run=False)["added"],1)
            self.assertEqual(import_snapshot(src,out,dry_run=False)["skipped_older_or_equal"],1)
            self.assertEqual(len(json.loads(out.read_text())),1)

    def test_newer_subscription_snapshot_updates_same_id(self):
        with tempfile.TemporaryDirectory() as folder:
            src=Path(folder)/"snapshot.json";out=Path(folder)/"feed.json"
            src.write_text(json.dumps(snapshot([alert()])))
            import_snapshot(src,out,dry_run=False)
            newer=alert(offset=10);newer["subscription_total_x"]="4.8"
            src.write_text(json.dumps(snapshot([newer])))
            result=import_snapshot(src,out,dry_run=False)
            self.assertEqual(result["updated"],1)
            self.assertEqual(json.loads(out.read_text())[0]["subscription_total_x"],"4.8")

    def test_denied_permission_does_not_modify_feed(self):
        with tempfile.TemporaryDirectory() as folder:
            src=Path(folder)/"snapshot.json";out=Path(folder)/"feed.json"
            out.write_text("[]")
            src.write_text(json.dumps(snapshot([alert()],allowed=False)))
            with self.assertRaises(ValidationError):import_snapshot(src,out,dry_run=False)
            self.assertEqual(out.read_text(),"[]")

    def test_mismatched_source_rejected(self):
        data=snapshot([alert()])
        data["alerts"][0]["source_name"]="Different source"
        with self.assertRaises(ValidationError):Snapshot.model_validate(data)

if __name__=="__main__":unittest.main()
