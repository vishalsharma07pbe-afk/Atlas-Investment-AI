import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from pydantic import ValidationError
from app.ingestion_quality import BatchRequest, inspect_batch

NOW = datetime(2026, 11, 14, 2, 0, tzinfo=timezone.utc)

def candidate(when="2026-11-14T01:59:00+00:00", instrument="NSE:TEST"):
    return {"instrument": instrument, "observed_at": when,
            "value": "125.50", "source_id": "TEST_SOURCE"}

def batch(rows, dataset="EQUITY_QUOTES", mode="MANUAL_IMPORT"):
    return BatchRequest(dataset=dataset, mode=mode, candidates=rows)

class IngestionQualityTests(unittest.TestCase):
    def test_recent_valid_batch_is_not_authorized_or_stored(self):
        with tempfile.TemporaryDirectory() as directory:
            result = inspect_batch(batch([candidate()]), NOW, Path(directory)/"missing.json")
        self.assertEqual(result["status"], "VALIDATED_NOT_AUTHORIZED")
        self.assertTrue(result["quality_passed"])
        self.assertFalse(result["authorized_to_ingest"])
        self.assertEqual(result["stored_records"], 0)
        self.assertIn("MANIFEST_NOT_CONFIGURED", result["authorization_blockers"])

    def test_stale_future_and_duplicate_observations(self):
        rows = [candidate(), candidate(), candidate("2026-11-14T01:40:00Z","NSE:OLD"),
                candidate("2026-11-14T02:02:00Z","NSE:FUTURE")]
        result = inspect_batch(batch(rows), NOW)
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual([p["reasons"][0] for p in result["problems"]],
                         ["DUPLICATE_OBSERVATION","STALE_OBSERVATION","FUTURE_OBSERVATION"])

    def test_bad_values_timezone_and_unexpected_fields(self):
        for row in [
            {**candidate(), "value": "NaN"},
            {**candidate(), "value": "-1"},
            {**candidate(), "observed_at": "2026-11-14T01:59:00"},
            {**candidate(), "secret": "never accept"},
        ]:
            with self.assertRaises(ValidationError):
                batch([row])

    def test_batch_limit_and_dataset_validation(self):
        with self.assertRaises(ValidationError):
            batch([])
        with self.assertRaises(ValidationError):
            batch([candidate()]*251)
        with self.assertRaises(ValidationError):
            batch([candidate()],dataset="UNKNOWN")

    def test_unverified_manifest_never_grants_access(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"sources.json"
            path.write_text(json.dumps({"version":1,"sources":[{
                "source_id":"TEST_SOURCE","dataset":"EQUITY_QUOTES",
                "mode":"MANUAL_IMPORT","purpose":"PERSONAL_RESEARCH",
                "permission_reference":"internal-review-ref",
                "reviewed_at":"2026-11-01T00:00:00Z",
                "valid_until":"2026-12-01T00:00:00Z"}]}))
            result=inspect_batch(batch([candidate()]),NOW,path)
        self.assertEqual(result["entitlement_status"],
                         "DECLARATION_PRESENT_REQUIRES_INDEPENDENT_VERIFICATION")
        self.assertFalse(result["authorized_to_ingest"])
        self.assertFalse(result["live_market_data_connected"])

if __name__=="__main__":
    unittest.main()
