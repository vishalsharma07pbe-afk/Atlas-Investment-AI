import unittest
from unittest.mock import patch
from app import analyst_source_discovery as d,chatgpt_plan as p,ai_failover as ai

class SourceDiscoveryTests(unittest.TestCase):
    def test_allowlisted_links_only(self):
        self.assertEqual(d.links(["https://www.nseindia.com/filing.pdf","https://nseindia.com.evil.test/a",
            "https://amfiindia.com@evil.test/a","http://sebi.gov.in/a","https://sebi.gov.in/a?token=secret",
            "https://www.nseindia.com/filing.pdf"]),["https://www.nseindia.com/filing.pdf"])
    def test_only_citations_from_complete_response(self):
        links=[]
        p.parse_stream(['data: {"type":"response.output_text.delta","delta":"ok"}',
            'data: {"type":"response.completed","response":{"output":[{"type":"message","content":[{"type":"output_text","annotations":[{"type":"url_citation","url":"https://sebi.gov.in/filing.pdf"}]}]}]}}'],source_links=links)
        self.assertEqual(links,["https://sebi.gov.in/filing.pdf"])
    def test_included_only_overrides_paid_switch_and_requires_free_confirmation(self):
        with patch.dict("os.environ",{"ATLAS_AI_INCLUDED_ONLY":"true","ATLAS_EXTERNAL_AI_ALLOWED":"true","ATLAS_GEMINI_ENABLED":"true",
            "ATLAS_GEMINI_FREE_TIER_CONFIRMED":"false","ATLAS_OPENAI_ENABLED":"true","ATLAS_OPENAI_RPM":"1","ATLAS_OPENAI_RPD":"1","ATLAS_PAID_AI_ALLOWED":"true"}):
            self.assertEqual(ai._configuration_status("GEMINI"),"FREE_TIER_CONFIRMATION_REQUIRED")
            self.assertEqual(ai._configuration_status("OPENAI"),"PAID_DISABLED")

    def test_receipt_records_exact_visible_identity_without_verifying_figures(self):
        from datetime import datetime,timezone
        now=datetime(2026,11,28,tzinfo=timezone.utc)
        url="https://www.nseindia.com/filing.html"
        ids=["INE002A01018","123456","789012"]
        data=b"<script>789012</script><p>INE002A01018 1234567</p>"
        v=d.document_receipt(url,ids,now,lambda u:("text/html",data))
        self.assertEqual(v["mentioned_identities"],["INE002A01018"])
        self.assertFalse(v["financial_facts_verified"])
        self.assertEqual(v["bytes"],len(data))
        self.assertIsNone(d.document_receipt("https://private.nseindia.com/filing.pdf",ids,now,lambda u:("application/pdf",b"%PDF-1.4")))
        self.assertIsNone(d.document_receipt(url,ids,now,lambda u:("application/pdf",b"not a pdf")))
        v=d.document_receipt(url,ids,now,lambda u:("application/pdf",b"%PDF-1.4"))
        self.assertEqual(v["status"],"PDF_BYTES_ONLY")
        self.assertFalse(v["financial_facts_verified"])
