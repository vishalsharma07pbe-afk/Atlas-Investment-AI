import importlib.util
import json
from pathlib import Path
import unittest

SPEC=importlib.util.spec_from_file_location("local_acceptance",Path(__file__).resolve().parents[2]/"scripts"/"local_research_acceptance.py")
a=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(a)

class AdvancedAcceptanceTests(unittest.TestCase):
    def fixture(self):
        d={"methodology":"UNIFIED-DECISION-1","status":"RESEARCH_CONTEXT_AVAILABLE","equity_companies":[],
           "equity_company_count":0,"equity_review_count":0,"ai_reviewed_company_count":0,"fund_categories":[]}
        overview={"unified_decision":d,"forward_earnings_validation":{"methodology":"QUARTER-PERSISTENCE-1",
          "status":"AWAITING_PUBLICATIONS","calibrated":False,"quarter_cohorts":[],"pending_count":0},
          "score_calibration":{"calibrated":False,"horizons":{h:{"temporal_diagnostics":{"calibrated":False}} for h in a.DAILY_HORIZONS}}}
        readiness={"research_jobs":{"jobs":[{"job":j,"status":"PENDING"} for j in a.ADVANCED_JOBS]}}
        review={"holding_count":0,"holdings":[],"portfolio_reassessment":{"holding_count":0,"scored_count":0,"reassess_count":0,"monitor_count":0,"evidence_needed_count":0}}
        session={"unified_decision":{"methodology":"UNIFIED-DECISION-1","scope":"CURRENT_SESSION","qualified":False,"state":"AWAITING_EVIDENCE"}}
        return readiness,overview,review,session
    def test_empty_contract_pass_is_not_evidence(self):
        args=self.fixture();out=a.advanced_audit(*args)
        self.assertEqual(out["status"],"PASS")
        self.assertEqual(out["observed_evidence"]["populated_portfolio_contract"],"NOT_OBSERVED")
        self.assertEqual(out["investment_qualification"],"NOT_CERTIFIED")
    def test_invalid_private_state_and_unknown_strings_do_not_leak(self):
        args=self.fixture();review=args[2]
        review.update(holding_count=1,holdings=[{"symbol":"PRIVATE_MARKER","unified_decision":{"scope":"PUBLIC","qualified":True}}])
        out=a.advanced_audit(*args)
        self.assertEqual(out["checks"]["owner_local_reassessment"],"BLOCKED")
        self.assertNotIn("PRIVATE_MARKER",json.dumps(out))
        args[1]["score_calibration"]["calibrated"]=True
        self.assertEqual(a.advanced_audit(*args)["checks"]["temporal_validation_contract"],"BLOCKED")
