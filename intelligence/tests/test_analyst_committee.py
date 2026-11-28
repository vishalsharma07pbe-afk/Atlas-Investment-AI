import unittest
from app import analyst_committee as c
from app import investment_analyst as a
from datetime import date
class CommitteeTest(unittest.TestCase):
    def test_model_cannot_invent_evidence_or_promote_adverse_fund(self):
        e={"S1":{"tier":"ADJUSTED_JOINT","allowed_reasons":["JOINT_SCREEN","LIMITED_EVIDENCE"]},
           "F1":{"tier":"DRIVER_REVIEW","allowed_reasons":["HISTORICAL_PEERS","DRIVER_RISK"]}}
        import json
        def row(k,decision,reason):
            return {"statement":json.dumps({"candidate":k,"decision":decision,"reason":reason}),"evidence_ids":[k]}
        r=c.validate({"findings":[row("S1","PRIORITIZE_REVIEW","JOINT_SCREEN"),row("F1","PRIORITIZE_REVIEW","HISTORICAL_PEERS"),row("S2","PRIORITIZE_REVIEW","JOINT_SCREEN")]},e)
        self.assertEqual(set(r),{"S1"})
        self.assertEqual(c.validate({"findings":[row("S1","PRIORITIZE_REVIEW","POSITIVE_SCENARIO")]},e),{})
        self.assertEqual(c.validate({"findings":[row("S1","PRIORITIZE_REVIEW","JOINT_SCREEN"),row("S1","DEFER_REVIEW","LIMITED_EVIDENCE")]},e),{})
    def test_fund_growth_is_original_weight_scenario_not_nav_forecast(self):
        d={"quarter":"2026-09-30","experimental_forward":{"status":"UNCALIBRATED_PERSISTENCE_EXPERIMENT","qualified":False,
          "observed_quarter":"2026-09-30","target_quarter":"2026-12-31","covered_weight_percent":80,
          "positive_joint_growth_weight_percent":65,"covered_subset_revenue_persistence_percent":10,"covered_subset_profit_persistence_percent":15}}
        v=a.fund_growth(d,date(2026,11,28))
        self.assertEqual(v["coverage_percent"],80)
        self.assertEqual(v["profit_yoy_percent"],15)
        self.assertIsNone(a.fund_growth(d,date(2027,1,1)))

    def test_scheduler_cache_disagreement_and_permission_revocation(self):
        import tempfile,sqlite3,json
        from datetime import datetime,timezone,timedelta
        from unittest.mock import patch
        from pathlib import Path
        now=datetime(2026,11,28,5,tzinfo=timezone.utc)
        def report():
            return {"status":"RESEARCH_AVAILABLE","research_date":"2026-11-28","stocks":[{"isin":"INE002A01018","tier":"ADJUSTED_JOINT",
              "as_of":"2026-11-27","qualified":False,"score":80,"risk":"MEDIUM","action":"RESEARCH_FOR_ENTRY",
              "observed_facts":{"earnings_growth_percent":20,"reported_pe":15,"reported_sector_pe":20,"private_balance":987654321}}],
              "funds":[],"private_notes":"do not transmit"}
        with tempfile.TemporaryDirectory() as tmp:
            def connect():
                return sqlite3.connect(Path(tmp)/"cache.sqlite")
            calls=[]
            def run(prompt,ids,providers):
                p=providers[0];calls.append(p)
                self.assertNotIn("987654321",prompt)
                self.assertNotIn("do not transmit",prompt)
                self.assertIn("GROWTH_AND_VALUATION",prompt)
                v={"candidate":"S1","decision":"PRIORITIZE_REVIEW" if p=="OLLAMA" else "DEFER_REVIEW",
                   "reason":"GROWTH_AND_VALUATION" if p=="OLLAMA" else "LIMITED_EVIDENCE"}
                return {"status":"MODEL_GROUNDED","provider":p,"response":{"findings":[{"statement":json.dumps(v),"evidence_ids":["S1"]}]}}
            with patch.object(c.ai,"providers",return_value=["OLLAMA","GEMINI"]):
                self.assertTrue(c.refresh(report(),connect,now,run))
                self.assertTrue(c.refresh(report(),connect,now+timedelta(minutes=15),run))
                self.assertEqual(calls,["OLLAMA","GEMINI"])
                r=c.attach(report(),connect,now+timedelta(minutes=16))
                self.assertEqual(r["stocks"][0]["action"],"WATCH_FOR_CONFIRMATION")
                self.assertEqual(r["stocks"][0]["ai_review"]["state"],"DISAGREEMENT")
                self.assertFalse(r["stocks"][0]["qualified"])
                changed=report();changed["stocks"][0]["observed_facts"]["earnings_growth_percent"]=21
                self.assertEqual(c.attach(changed,connect,now+timedelta(minutes=17))["committee"]["reviewed_providers"],0)
                self.assertEqual(c.attach(report(),connect,now+timedelta(days=2))["committee"]["reviewed_providers"],0)
            with patch.object(c.ai,"providers",return_value=[]):
                self.assertEqual(c.attach(report(),connect,now+timedelta(minutes=17))["committee"]["reviewed_providers"],0)
