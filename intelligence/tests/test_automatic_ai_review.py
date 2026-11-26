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
                    {"findings":[{"statement":'{"path":"/OBS/observations/atr_percent","value":2}', "evidence_ids":["OBS"]}]}}
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

    def test_review_includes_only_allowlisted_same_company_financial_trends(self):
        item=snapshot()["sections"][0]["result"]["horizons"]["SWING"]["candidates"][0]
        item["isin"]="INE002A01018"
        item["company_evidence"]={"isin":item["isin"],"financial_trends":{"items":[
            {"metric":"REVENUE","previous_year":2025,"latest_year":2026,"direction":"INCREASED",
             "latest_period_may_be_stale":False,"change_percent":8.2,"private_notes":"never forward"},
            {"metric":"NET_PROFIT","previous_year":2022,"latest_year":2023,"direction":"INCREASED",
             "latest_period_may_be_stale":True,"change_percent":99}]}}
        item["matched_strategy_replay"]={"as_of":item["as_of"],"status":"REPLAY_OBSERVED","trades":4,
            "cost_scenarios":[{"cost_bps_per_side":30,"net_return_percent":-2,"max_drawdown_percent":-5,"notes":"secret notes"}]}
        pack=review.evidence(item,"SWING")
        self.assertEqual([r["metric"] for r in pack["financial_trends"]],["REVENUE"])
        self.assertEqual(pack["historical_replay"]["trades"],4)
        def runner(prompt,ids,providers):
            self.assertEqual(set(ids),{"OBS","LIMITS","FUND","REPLAY"})
            self.assertNotIn("never forward",prompt)
            self.assertNotIn("secret notes",prompt)
            return {"status":"MODEL_GROUNDED","provider":providers[0],"response":{
                "findings":[{"statement":'{"path":"/FUND/0/direction","value":"INCREASED"}',"evidence_ids":["FUND"]}]}}
        self.assertIsNotNone(review._review(pack,"OLLAMA",runner))
        item["company_evidence"]["isin"]="INE009A01021"
        self.assertNotIn("financial_trends",review.evidence(item,"SWING"))


    def test_five_provider_role_committee_resumes_in_bounded_batches(self):
        calls=[]
        def runner(prompt,ids,providers):
            calls.append((providers[0],prompt))
            return {"status":"MODEL_GROUNDED","provider":providers[0],"response":{
                "findings":[{"statement":'{"path":"/OBS/observations/atr_percent","value":2}',"evidence_ids":["OBS"]}]}}
        with patch.dict(os.environ,{"ATLAS_AUTOMATIC_EXTERNAL_AI_ALLOWED":"true",
            "ATLAS_AI_PROVIDER_ORDER":"GEMINI,GROQ,OPENAI,XAI,OLLAMA"}),patch.object(review.ai_failover,"_enabled",return_value=True):
            for expected in (2,4,5,5):
                review.refresh(snapshot(),research._connect,runner)
                self.assertEqual(len(calls),expected)
            result=review.attach(snapshot(),research._connect)
            item=result["sections"][0]["result"]["horizons"]["SWING"]["candidates"][0]
            committee=item["ai_review"]["committee"]
            self.assertEqual(committee["reviewed_count"],5)
            self.assertEqual(committee["status"],"ALL_CONFIGURED_REVIEWS_RETURNED")
            self.assertEqual(committee["agreement_status"],"SHARED_MATCHED_OBSERVATIONS_ONLY")
            self.assertEqual(committee["uncited_domains"],["LIMITS"])
            self.assertEqual([p for p,_ in calls],["OLLAMA","GEMINI","GROQ","OPENAI","XAI"])
            self.assertEqual(len({m["role"] for m in committee["members"]}),5)
            self.assertTrue(all("Assigned independent review role" in prompt for _,prompt in calls))
            with patch.dict(os.environ,{"ATLAS_AUTOMATIC_EXTERNAL_AI_ALLOWED":"false"}):
                changed=review.attach(snapshot(),research._connect)
                self.assertNotIn("ai_review",changed["sections"][0]["result"]["horizons"]["SWING"]["candidates"][0])

    def test_failed_member_does_not_suppress_later_members_or_repeat_immediately(self):
        calls=[]
        def runner(prompt,ids,providers):
            provider=providers[0]
            calls.append(provider)
            if provider=="GEMINI":
                return {"status":"MODEL_UNAVAILABLE"}
            return {"status":"MODEL_GROUNDED","provider":provider,"response":{
                "findings":[{"statement":'{"path":"/LIMITS/0","value":"Live liquidity"}',"evidence_ids":["LIMITS"]}]}}
        with patch.dict(os.environ,{"ATLAS_AUTOMATIC_EXTERNAL_AI_ALLOWED":"true",
            "ATLAS_AI_PROVIDER_ORDER":"OLLAMA,GEMINI,GROQ"}),patch.object(review.ai_failover,"_enabled",return_value=True):
            for _ in range(3):
                review.refresh(snapshot(),research._connect,runner)
            self.assertEqual(calls,["OLLAMA","GEMINI","GROQ"])
            item=review.attach(snapshot(),research._connect)["sections"][0]["result"]["horizons"]["SWING"]["candidates"][0]
            committee=item["ai_review"]["committee"]
            self.assertEqual(committee["status"],"PARTIAL_REVIEWS")
            self.assertEqual(committee["members"][1]["status"],"NO_USABLE_REVIEW")
            self.assertEqual(committee["reviewed_count"],2)

    def test_changed_model_and_disabled_permissions_clear_attached_review(self):
        data=snapshot()
        def runner(prompt,ids,providers):
            return {"status":"MODEL_GROUNDED","provider":providers[0],"response":{"findings":[
                {"statement":'{"path":"/OBS/observations/atr_percent","value":2}',"evidence_ids":["OBS"]}]}}
        with patch.object(review.ai_failover,"_enabled",return_value=True),patch.dict(os.environ,{"ATLAS_OLLAMA_MODEL":"first"}):
            review.refresh(data,research._connect,runner)
            review.attach(data,research._connect)
            item=data["sections"][0]["result"]["horizons"]["SWING"]["candidates"][0]
            self.assertIn("ai_review",item)
            with patch.dict(os.environ,{"ATLAS_OLLAMA_MODEL":"second"}):
                review.attach(data,research._connect)
                self.assertNotIn("ai_review",item)
            review.attach(data,research._connect)
            self.assertIn("ai_review",item)
            with patch.dict(os.environ,{"ATLAS_AUTOMATIC_AI_REVIEW_ENABLED":"false"}):
                review.attach(data,research._connect)
                self.assertNotIn("ai_review",item)
