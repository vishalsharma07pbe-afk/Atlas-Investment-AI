import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from app.ipo_provider_audit import run_audited_import,_append_audit

class ImportAuditTests(unittest.TestCase):
    def test_successful_dry_run_audited_without_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);audit=root/"audit.json"
            data={"added":2,"updated":1,"skipped_older_or_equal":0,"retained":3,
                "input_sha256":"a"*64}
            with patch("app.ipo_provider_audit.sync_provider",return_value=data) as sync:
                result=run_audited_import(root/"config.json",root/"alerts.json",audit)
            self.assertEqual(result["outcome"],"SUCCESS")
            self.assertEqual(result["mode"],"DRY_RUN")
            self.assertFalse(sync.call_args.kwargs["apply"])
            self.assertEqual(len(json.loads(audit.read_text())),1)
            self.assertNotIn("token",audit.read_text().lower())
    def test_failure_audited_without_exception_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);audit=root/"audit.json"
            with patch("app.ipo_provider_audit.sync_provider",side_effect=ValueError("SECRET-BEARER-TOKEN")):
                result=run_audited_import(root/"config.json",root/"alerts.json",audit,apply=True)
            self.assertEqual(result["outcome"],"FAILED")
            self.assertEqual(result["mode"],"APPLY")
            self.assertEqual(result["error_category"],"ValueError")
            self.assertNotIn("SECRET-BEARER-TOKEN",audit.read_text())
    def test_audit_history_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"audit.json"
            for i in range(110):_append_audit(path,{"attempt":i})
            entries=json.loads(path.read_text())
            self.assertEqual(len(entries),100)
            self.assertEqual(entries[0]["attempt"],10)
    def test_refuses_same_output_and_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"same.json"
            with self.assertRaises(ValueError):run_audited_import(path,path,path)
if __name__=="__main__":unittest.main()
