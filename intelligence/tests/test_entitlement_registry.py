import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.entitlement_registry import (
    entitlement_preflight, entitlement_summary, validate_manifest, load_manifest,
)

NOW = datetime.now(timezone.utc)
def stamp(delta):
    return (NOW + timedelta(days=delta)).isoformat()

def entry(**changes):
    result = dict(source_id="EXAMPLE_VENDOR", dataset="EQUITY_QUOTES", mode="STREAM",
                  purpose="PERSONAL_RESEARCH", permission_reference="local-contract-reference",
                  valid_until=stamp(10), reviewed_at=stamp(-1))
    result.update(changes)
    return result

class EntitlementRegistryTests(unittest.TestCase):
    def write(self, folder, content):
        path = Path(folder) / "sources.json"
        path.write_text(json.dumps(content), encoding="utf-8")
        return path

    def test_absent_manifest_blocks(self):
        with tempfile.TemporaryDirectory() as folder:
            result = entitlement_preflight("EQUITY_QUOTES", "STREAM", path=Path(folder)/"absent.json")
            self.assertFalse(result["automatic_collection_enabled"])
            self.assertIn("MANIFEST_NOT_CONFIGURED", result["blockers"])

    def test_declared_scope_never_authorizes_automation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.write(folder, {"version": 1, "sources": [entry()]})
            result = entitlement_preflight("EQUITY_QUOTES", "STREAM", path=path)
            self.assertEqual(result["status"], "DECLARATION_PRESENT_REQUIRES_INDEPENDENT_VERIFICATION")
            self.assertFalse(result["automatic_collection_enabled"])
            self.assertFalse(result["independently_verified"])
            self.assertNotIn("local-contract-reference", str(result))
            self.assertNotIn("local-contract-reference", str(entitlement_summary(path)))

    def test_expired_and_wrong_scope_block(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.write(folder, {"version": 1, "sources": [entry(valid_until=stamp(-1))]})
            self.assertIn("ENTITLEMENT_EXPIRED", entitlement_preflight("EQUITY_QUOTES","STREAM",path=path)["blockers"])
            self.assertIn("NO_MATCHING_ENTITLEMENT_DECLARATION", entitlement_preflight("MF_NAV","STREAM",path=path)["blockers"])

    def test_malformed_and_duplicate_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "INVALID_OR_DUPLICATE_SOURCE_ID"):
            validate_manifest({"version":1,"sources":[entry(),entry()]})
        with tempfile.TemporaryDirectory() as folder:
            path = self.write(folder, {"version":1,"sources":[entry(reviewed_at="2026-01-01")]})
            self.assertEqual(load_manifest(path)[1], "MANIFEST_INVALID")
            self.assertFalse(entitlement_preflight("EQUITY_QUOTES","STREAM",path=path)["automatic_collection_enabled"])

    def test_invalid_scope_rejected(self):
        with self.assertRaisesRegex(ValueError, "INVALID_REQUESTED_SCOPE"):
            entitlement_preflight("NOT_REAL","STREAM")

if __name__ == "__main__":
    unittest.main()
