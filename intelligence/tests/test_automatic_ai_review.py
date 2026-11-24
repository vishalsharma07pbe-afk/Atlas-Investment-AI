import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from app import automatic_ai_review as review, autonomous_research as research

def snapshot():
    item={"symbol":"TEST","exchange":"NSE","as_of":"2026-11-23","close":100,
          "history_count":60,"atr_percent":2,"adjustment_status":"ADJUSTED",
          "private_balance":123456789,"notes":"never forward"}
    return {"enabled":True,"sections":[{"section":"NSE","status":"READY",
        "result":{"horizons":{"SWING":{"candidates":[item]}}}}]}

class AutomaticAiReviewTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        env=patch.dict(os.environ,{"ATLAS_RESEARCH_SNAPSHOT_DB":temp.name+"/research.sqlite3",
             "ATLAS_AUTOMATIC_AI_REVIEW_ENABLED":"true","ATLAS_AUTOMATIC_EXTERNAL_AI_ALLOWED":"false",
             "ATLAS_AI_PROVIDER_ORDER":"GEMINI,OLLAMA"})
        env.start()
        self.addCleanup(env.stop)

    def test_local_first_opt_in_and_cached_public_review(self):
        calls=[]
        def runner(prompt, ids, providers):
            calls.append((prompt,providers))
            return {"status":"MODEL_GROUNDED","provider":providers[0],"response":
                    {"findings":[{"statement":"ATR is 2 percent.", "evidence_ids":["OBS"]}]}}
        with patch.object(review.ai_failover,"_enabled",return_value=True):
            self.assertEqual(review.providers(),["OLLAMA"])
            review.refresh(snapshot(),research._connect,runner)
            review.refresh(snapshot(),research._connect,runner)
            self.assertEqual(len(calls),1)
            self.assertNotIn("123456789",calls[0][0])
            self.assertNotIn("never forward",calls[0][0])
            result=review.attach(snapshot(),research._connect)
            item=result["sections"][0]["result"]["horizons"]["SWING"]["candidates"][0]
            self.assertEqual(item["ai_review"]["reviews"][0]["provider"],"OLLAMA")
            changed=snapshot()
            changed["sections"][0]["result"]["horizons"]["SWING"]["candidates"][0]["close"]=110
            item=review.attach(changed,research._connect)["sections"][0]["result"]["horizons"]["SWING"]["candidates"][0]
            self.assertNotIn("ai_review",item)

    def test_two_provider_limit_and_reject_unsupported_citations(self):
        calls=[]
        def runner(prompt, ids, providers):
            calls.append(providers[0])
            return {"status":"MODEL_GROUNDED","provider":providers[0],"response":
                    {"findings":[{"statement":"Unsupported claim", "evidence_ids":["FAKE"]}]}}
        with patch.dict(os.environ,{"ATLAS_AUTOMATIC_EXTERNAL_AI_ALLOWED":"true"}), patch.object(review.ai_failover,"_enabled",return_value=True):
            review.refresh(snapshot(),research._connect,runner)
            review.refresh(snapshot(),research._connect,runner)
            self.assertEqual(calls,["OLLAMA","GEMINI"])
            item=review.attach(snapshot(),research._connect)["sections"][0]["result"]["horizons"]["SWING"]["candidates"][0]
            self.assertNotIn("ai_review",item)

    def test_no_calls_for_failed_snapshot_or_disabled_automation(self):
        data=snapshot()
        data["sections"][0]["status"]="FAILED"
        with patch.object(review.ai_failover,"_enabled",return_value=True):
            review.refresh(data,research._connect,lambda *a,**kw:self.fail("provider called"))
            with patch.dict(os.environ,{"ATLAS_AUTOMATIC_AI_REVIEW_ENABLED":"false"}):
                review.refresh(snapshot(),research._connect,lambda *a,**kw:self.fail("provider called"))
