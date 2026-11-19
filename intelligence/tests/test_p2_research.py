import unittest
from datetime import datetime, timezone

from app.p2_research import (AdvancedScreenRequest, GroundedResearchRequest,
                             ResearchEvidence, ScreenCandidate, advanced_screen,
                             grounded_answer)


class GroundedResearchTests(unittest.TestCase):
    def evidence(self):
        now = datetime.now(timezone.utc)
        return [
            ResearchEvidence(id="TECH1", domain="TECHNICALS", statement="Momentum is positive.",
                             source_name="Validated daily candles", observed_at=now),
            ResearchEvidence(id="RISK1", domain="RISK", statement="Volatility is elevated.",
                             source_name="ATLAS calculation", observed_at=now),
        ]

    def test_fallback_cites_every_finding(self):
        result = grounded_answer(GroundedResearchRequest(question="What are the risks?",
                                 asset_name="TEST", asset_type="STOCK", evidence=self.evidence(),
                                 use_ai=False))
        source_ids = {source["id"] for source in result["sources"]}
        self.assertTrue(result["findings"])
        self.assertTrue(all(set(item["evidence_ids"]) <= source_ids for item in result["findings"]))
        self.assertIn("FUNDAMENTALS", result["coverage"]["missing_expected_domains"])

    def test_rejects_model_citation_not_in_pack(self):
        def unsafe_runner(_prompt, _ids):
            return {"status": "MODEL_GROUNDED", "provider": "TEST", "response": {
                "answer": "Unsupported", "findings": [{"statement": "Claim", "evidence_ids": ["FAKE"]}],
                "uncertainties": [], "follow_up_questions": []}}
        result = grounded_answer(GroundedResearchRequest(question="Explain", asset_name="TEST",
                                 asset_type="STOCK", evidence=self.evidence()), unsafe_runner)
        self.assertEqual(result["status"], "MODEL_RESPONSE_REJECTED")
        self.assertNotIn("FAKE", {eid for row in result["findings"] for eid in row["evidence_ids"]})


class AdvancedScreenTests(unittest.TestCase):
    def test_missing_required_factor_fails_closed(self):
        request = AdvancedScreenRequest(candidates=[ScreenCandidate(
            id=1, symbol="AAA", exchange="NSE", as_of="2026-11-18",
            momentum_20d_percent=10, roe_percent=None)], min_momentum_percent=5,
            min_roe_percent=12)
        result = advanced_screen(request)
        self.assertEqual(result["matched_count"], 0)
        self.assertEqual(result["excluded"][0]["missing_required_factors"], ["roe_percent"])

    def test_returns_explainable_matches(self):
        request = AdvancedScreenRequest(candidates=[ScreenCandidate(
            id=1, symbol="AAA", exchange="NSE", as_of="2026-11-18",
            momentum_20d_percent=10, roe_percent=18, pe_ratio=20)],
            min_momentum_percent=5, min_roe_percent=12, max_pe_ratio=30)
        result = advanced_screen(request)
        self.assertEqual(result["matched_count"], 1)
        self.assertIn("roe_percent", result["results"][0]["matched_factors"])


if __name__ == "__main__":
    unittest.main()
