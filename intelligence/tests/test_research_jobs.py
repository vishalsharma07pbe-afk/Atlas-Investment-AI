import os
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app import autonomous_research as research, research_jobs as jobs


class DurableResearchJobsTests(unittest.TestCase):
    def setUp(self):
        root=tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        env=patch.dict(os.environ,{"ATLAS_RESEARCH_SNAPSHOT_DB":root.name+"/research.sqlite",
                                   "ATLAS_AUTONOMOUS_RESEARCH_ENABLED":"true"})
        env.start()
        self.addCleanup(env.stop)
        self.connect=research._connect
        self.clock=1800000000.0

    def states(self,definitions,instant=None):
        return {r["job"]:r for r in jobs.status(self.connect,definitions,self.clock if instant is None else instant)["jobs"]}

    def test_priority_claim_and_persisted_cadence(self):
        definitions={"LOW":20,"HIGH":0}
        job,token=jobs.claim(self.connect,definitions,self.clock)
        self.assertEqual(job,"HIGH")
        self.assertIsNone(jobs.claim(self.connect,definitions,self.clock+1))
        self.assertTrue(jobs.finish(self.connect,job,token,self.clock+2,300,"PASS_COMPLETED"))
        job,token=jobs.claim(self.connect,definitions,self.clock+3)
        self.assertEqual(job,"LOW")
        jobs.finish(self.connect,job,token,self.clock+4,300,"PASS_COMPLETED")
        self.assertIsNone(jobs.claim(self.connect,definitions,self.clock+299))
        self.assertEqual(jobs.claim(self.connect,definitions,self.clock+302)[0],"HIGH")

    def test_expired_lease_recovery_and_late_finish_rejection(self):
        definitions={"ONLY":1}
        job,old=jobs.claim(self.connect,definitions,self.clock)
        expiry=self.clock+jobs.LEASE_SECONDS
        self.assertEqual(self.states(definitions,expiry)["ONLY"]["status"],"INTERRUPTED")
        new_job,new=jobs.claim(self.connect,definitions,expiry)
        self.assertEqual(new_job,job)
        self.assertNotEqual(old,new)
        self.assertFalse(jobs.finish(self.connect,job,old,expiry,300,"PASS_COMPLETED"))
        self.assertTrue(jobs.finish(self.connect,job,new,expiry+1,300,"PASS_COMPLETED"))
        self.assertEqual(self.states(definitions,expiry+1)["ONLY"]["interrupted_attempts"],1)

    def test_failure_backoff_and_independent_jobs(self):
        definitions={"A":0,"B":1}
        job,token=jobs.claim(self.connect,definitions,self.clock)
        jobs.finish(self.connect,job,token,self.clock,300,"FAILED")
        failed=self.states(definitions)["A"]
        self.assertEqual(failed["consecutive_failures"],1)
        self.assertEqual(failed["error_code"],"RESEARCH_JOB_FAILED")
        job,token=jobs.claim(self.connect,definitions,self.clock)
        self.assertEqual(job,"B")
        jobs.finish(self.connect,job,token,self.clock,300,"PASS_COMPLETED")
        self.assertIsNone(jobs.claim(self.connect,definitions,self.clock+59))
        job,token=jobs.claim(self.connect,definitions,self.clock+60)
        jobs.finish(self.connect,job,token,self.clock+60,300,"FAILED")
        self.assertIsNone(jobs.claim(self.connect,definitions,self.clock+179))
        job,token=jobs.claim(self.connect,definitions,self.clock+180)
        jobs.finish(self.connect,job,token,self.clock+180,300,"PASS_COMPLETED")
        self.assertEqual(self.states(definitions)["A"]["consecutive_failures"],0)

    def test_scheduler_dispatch_failure_preserves_other_sections(self):
        def market(exchange):
            if exchange=="NSE":
                raise RuntimeError("private-token-never-persist")
            return {"exchange":exchange}
        with patch.object(research.fund_disclosures,"permitted",return_value=False), \
             patch.object(research.research_calendar,"refresh"), \
             patch.object(research.portfolio_thesis,"enabled",return_value=False), \
             patch.object(research,"market_snapshot",side_effect=market), \
             patch.object(research,"fund_snapshot",side_effect=lambda c:{"category":c}), \
             patch.object(research.automatic_institutional,"permitted",return_value=False), \
             patch.object(research.automatic_company_evidence,"permitted",return_value=False), \
             patch.object(research.automatic_news,"permitted",return_value=False), \
             patch.object(research.automatic_ai_review,"enabled",return_value=False), \
             patch.object(research.watch_outcomes,"refresh"), \
             patch.object(research.automatic_strategy_validation,"refresh"), \
             patch.object(research,"now",return_value=datetime.fromtimestamp(self.clock,timezone.utc)):
            for _ in jobs.definitions(research.SECTIONS):
                self.assertTrue(research.run_one_job(300))
            self.assertFalse(research.run_one_job(300))
            snapshot=research.read_snapshot(False)
            self.assertEqual(snapshot["sections"][0]["status"],"FAILED")
            self.assertEqual(snapshot["sections"][1]["status"],"READY")
            state=research.job_status()
            self.assertNotIn("private-token",str(state))
            states={j["job"]:j["status"] for j in state["jobs"]}
            self.assertEqual(states["SECTION:NSE"],"FAILED")
            self.assertEqual(states["SECTION:BSE"],"PASS_COMPLETED")

    def test_dependencies_and_permission_gate_without_network_calls(self):
        with patch.object(research.automatic_company_evidence,"permitted",return_value=True), \
             patch.object(research.automatic_company_evidence,"refresh") as refresh:
            self.assertEqual(research._execute_job("COMPANY_EVIDENCE"),"WAITING_EVIDENCE")
            refresh.assert_not_called()
            research._save("BSE",{"exchange":"BSE"})
            self.assertEqual(research._execute_job("COMPANY_EVIDENCE"),"PASS_COMPLETED")
            refresh.assert_called_once()
        with patch.object(research.automatic_news,"permitted",return_value=False), \
             patch.object(research.automatic_news,"refresh") as refresh:
            self.assertEqual(research._execute_job("COMPANY_NEWS"),"DISABLED_OR_NOT_AUTHORIZED")
            refresh.assert_not_called()

    def test_disabled_scheduler_status_excludes_persisted_states(self):
        with patch.dict(os.environ,{"ATLAS_AUTONOMOUS_RESEARCH_ENABLED":"false"}):
            self.assertEqual(research.job_status(),{"status":"DISABLED","jobs":[]})
