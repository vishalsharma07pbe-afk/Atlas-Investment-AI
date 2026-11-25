import json
import unittest
from app import ai_claims as claims, automatic_ai_review as review

EVIDENCE={"OBS":{"observations":{"atr_percent":2,"close":100}},"LIMITS":["Live liquidity"],
          "REGIME":{"trend":"RISING"}}
def claim(path,value,citation=None):
    return {"statement":json.dumps({"path":path,"value":value}),
            "evidence_ids":[citation or path.split("/")[1]]}

class ClaimAuditTests(unittest.TestCase):
    def test_exact_value_type_and_scope(self):
        result=claims.audit(EVIDENCE,[
            claim("/OBS/observations/atr_percent",2.0),
            claim("/OBS/observations/close",True),
            claim("/REGIME/trend","FALLING"),
            claim("/LIMITS/0","Live liquidity","OBS"),
            claim("/OBS/private_balance",100),
            {"statement":"Fabricated conclusion","evidence_ids":["OBS"]}])
        self.assertEqual(result["claims"],[
            {"path":"/OBS/observations/atr_percent","status":"MATCHED"},
            {"path":"/OBS/observations/close","status":"CONTRADICTED"},
            {"path":"/REGIME/trend","status":"CONTRADICTED"}])
        self.assertEqual(result["rejected_count"],3)
        self.assertEqual(len(result["findings"]),1)
        self.assertNotIn("FALLING",json.dumps(result))
        self.assertNotIn("Fabricated conclusion",json.dumps(result))
    def test_duplicate_and_unknown_values_are_not_accepted(self):
        result=claims.audit(EVIDENCE,[claim("/OBS/observations/close",100),
            claim("/OBS/observations/close",99),
            {"statement":'{"path":"/LIMITS/0","value":"Live liquidity","value":"wrong"}',"evidence_ids":["LIMITS"]}])
        self.assertEqual(result["findings"],[])
        self.assertEqual(result["duplicate_count"],2)
        self.assertEqual(result["rejected_count"],1)
    def test_conflict_and_shared_observations_not_majority_verdict(self):
        a=claims.audit(EVIDENCE,[claim("/OBS/observations/close",100),claim("/REGIME/trend","RISING")])
        b=claims.audit(EVIDENCE,[claim("/OBS/observations/close",90),claim("/REGIME/trend","RISING")])
        result=claims.compare(EVIDENCE,[{"provider":"OLLAMA","claim_audit":a},{"provider":"GEMINI","claim_audit":b}])
        self.assertEqual(result["status"],"CONFLICTING_ASSERTIONS")
        self.assertEqual(result["matched_count"],3)
        self.assertEqual(result["contradicted_count"],1)
        self.assertEqual(result["conflicts"][0]["contradicting_providers"],["GEMINI"])
        self.assertEqual(result["shared_matches"][0]["path"],"/REGIME/trend")
        self.assertNotIn("majority_action",result)
    def test_review_withholds_wrong_and_prose(self):
        pack=review.evidence({"symbol":"TEST","exchange":"NSE","as_of":"2026-11-24","close":100,
            "history_count":60,"atr_percent":2,"adjustment_status":"ADJUSTED"},"SWING")
        def runner(prompt,ids,providers):
            return {"status":"MODEL_GROUNDED","provider":providers[0],"response":{"findings":[
                claim("/OBS/observations/close",150),
                {"statement":"Unverified prediction","evidence_ids":["OBS"]}]}}
        result=review._review(pack,"OLLAMA",runner)
        self.assertEqual(result["findings"],[])
        self.assertEqual(result["claim_audit"]["claims"][0]["status"],"CONTRADICTED")
        self.assertEqual(result["claim_audit"]["rejected_count"],1)
        self.assertNotIn("Unverified prediction",json.dumps(result))
