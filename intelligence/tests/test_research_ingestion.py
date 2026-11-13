import unittest
from datetime import date
from pydantic import ValidationError
from app.research_ingestion import IngestionReview,audit_manifests

def manifest(**overrides):
    base={"source":"GROWW","acquisition_mode":"USER_SUBMITTED",
        "access_authorized":True,"redistribution_authorized":False,
        "document_id":"report-1","retrieved_on":"2026-11-13",
        "published_on":"2026-11-12","report_url":"https://example.org/report",
        "content_sha256":"a"*64}
    base.update(overrides)
    return base

class ResearchIngestionTests(unittest.TestCase):
    def test_manifest_remains_quarantined_even_with_permission_declarations(self):
        result=audit_manifests(IngestionReview(manifests=[manifest(
            redistribution_authorized=True)]))
        self.assertEqual(result["database_writes"],0)
        self.assertEqual(result["entries"][0]["status"],"QUARANTINE_REQUIRED")
        self.assertIn("DOCUMENT_CONTENT_NOT_INDEPENDENTLY_VERIFIED",result["entries"][0]["blockers"])

    def test_duplicate_documents_and_unauthorized_access(self):
        data=IngestionReview(manifests=[manifest(access_authorized=False),
            manifest(access_authorized=False)])
        result=audit_manifests(data)
        self.assertIn("DUPLICATE_DOCUMENT_ID",result["entries"][1]["blockers"])
        self.assertIn("ACCESS_RIGHTS_NOT_CONFIRMED",result["entries"][0]["blockers"])

    def test_api_connector_not_verified(self):
        result=audit_manifests(IngestionReview(manifests=[
            manifest(source="ZERODHA",acquisition_mode="LICENSED_API")]))
        self.assertIn("AUTOMATED_SOURCE_CONNECTOR_NOT_VERIFIED",result["entries"][0]["blockers"])

    def test_invalid_hash_and_chronology_rejected(self):
        with self.assertRaises(ValidationError):
            IngestionReview(manifests=[manifest(content_sha256="invalid")])
        with self.assertRaises(ValidationError):
            IngestionReview(manifests=[manifest(published_on="2026-11-14")])

if __name__=="__main__":unittest.main()
