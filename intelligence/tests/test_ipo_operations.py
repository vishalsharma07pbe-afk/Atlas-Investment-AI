import json,tempfile,unittest
from pathlib import Path
from app.ipo_operations import import_history

class OperationsTests(unittest.TestCase):
    def test_missing_audit_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=import_history(Path(tmp)/"absent.json")
            self.assertEqual(result["status"],"NOT_CONFIGURED")
            self.assertEqual(result["total"],0)
    def test_history_is_newest_first_and_allowlisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"history.json"
            path.write_text(json.dumps([
                {"mode":"DRY_RUN","outcome":"SUCCESS","attempted_at":"first","secret":"do-not-show"},
                {"mode":"APPLY","outcome":"FAILED","attempted_at":"second","error_category":"ValueError","token":"secret"}]))
            result=import_history(path)
            self.assertEqual(result["attempts"][0]["attempted_at"],"second")
            self.assertEqual(result["total"],2)
            self.assertNotIn("secret",json.dumps(result))
            self.assertNotIn("token",json.dumps(result))
    def test_invalid_history_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"history.json"
            path.write_text(json.dumps([{"mode":"APPLY","outcome":"UNKNOWN"}]))
            with self.assertRaises(ValueError):import_history(path)
if __name__=="__main__":unittest.main()
