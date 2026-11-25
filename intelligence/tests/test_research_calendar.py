import os
import tempfile
import unittest
from contextlib import closing
from datetime import datetime,timedelta,timezone
from unittest.mock import patch

from app import autonomous_research as research, research_calendar as calendar, research_jobs as jobs


class ResearchCalendarTests(unittest.TestCase):
    def setUp(self):
        root=tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        env=patch.dict(os.environ,{"ATLAS_RESEARCH_SNAPSHOT_DB":root.name+"/research.sqlite"})
        env.start()
        self.addCleanup(env.stop)
        self.instant=datetime(2026,11,25,2,30,tzinfo=timezone.utc) # 08:00 IST
        self.open=datetime(2026,11,25,3,45,tzinfo=timezone.utc)
        self.close=datetime(2026,11,25,10,0,tzinfo=timezone.utc)
        self.definitions=jobs.definitions(research.SECTIONS)
        # Populate the real durable ledger with completed jobs.
        for _ in self.definitions:
            job,token=jobs.claim(research._connect,self.definitions,self.instant.timestamp()-60)
            jobs.finish(research._connect,job,token,self.instant.timestamp()-60,900,"PASS_COMPLETED")

    def payload(self,instant,phase="PRE_MARKET",other="CLOSED"):
        def row(exchange,state):
            return {"exchange":exchange,"session_date":instant.astimezone(calendar.IST).date().isoformat(),
                    "phase":state,"open_at":self.open.isoformat() if state in calendar.TIMED else None,
                    "close_at":self.close.isoformat() if state in calendar.TIMED else None}
        return {"observed_at":instant.isoformat(),"timezone":"Asia/Kolkata",
                "sessions":[row("NSE",phase),row("BSE",other)]}

    def refresh(self,instant,phase="PRE_MARKET",other="CLOSED"):
        return calendar.refresh(research._connect,lambda path:self.payload(instant,phase,other),instant)

    def due(self,job):
        with closing(research._connect()) as db:
            return db.execute("SELECT next_due FROM research_job_state WHERE job=?",(job,)).fetchone()[0]

    def test_pre_market_transition_prioritizes_selected_jobs_once(self):
        before=self.due("SECTION:BSE")
        self.refresh(self.instant)
        self.assertEqual(self.due("SECTION:NSE"),self.instant.timestamp())
        self.assertEqual(self.due("PORTFOLIO_REVIEW"),self.instant.timestamp())
        self.assertEqual(self.due("SECTION:BSE"),before)
        self.assertEqual(self.due("SECTION:LARGE_CAP"),before)
        with closing(research._connect()) as db,db:
            db.execute("UPDATE research_job_state SET next_due=? WHERE job='PORTFOLIO_REVIEW'",(before,))
        self.refresh(self.instant+timedelta(seconds=60))
        self.assertEqual(self.due("PORTFOLIO_REVIEW"),before)

    def test_post_market_and_market_hours_have_distinct_triggers(self):
        self.refresh(self.open,"MARKET_HOURS")
        self.assertLess(self.due("INSTITUTIONAL_FLOWS"),self.open.timestamp())
        with closing(research._connect()) as db,db:
            db.execute("UPDATE research_job_state SET next_due=?",(self.close.timestamp()+900,))
        self.refresh(self.close,"POST_MARKET")
        self.assertEqual(self.due("INSTITUTIONAL_FLOWS"),self.close.timestamp())
        self.assertEqual(self.due("STRATEGY_REPLAY"),self.close.timestamp())

    def test_calendar_missing_or_closed_does_not_nudge(self):
        prior=self.due("SECTION:NSE")
        self.refresh(self.instant,"CALENDAR_UNVERIFIED","SPECIAL_SESSION_UNSUPPORTED")
        self.assertEqual(self.due("SECTION:NSE"),prior)
        self.assertEqual(calendar.read(research._connect,self.instant)["sessions"][0]["phase"],"CALENDAR_UNVERIFIED")

    def test_phase_rechecked_at_boundary_and_staleness(self):
        near=self.open-timedelta(seconds=30)
        self.refresh(near)
        self.assertEqual(calendar.read(research._connect,near)["status"],"STORED_SESSION_CONTEXT")
        self.assertEqual(calendar.read(research._connect,self.open)["sessions"],[])
        self.assertEqual(calendar.read(research._connect,near+timedelta(minutes=4))["sessions"],[])

    def test_inconsistent_identity_or_phase_rejected(self):
        with self.assertRaisesRegex(ValueError,"CALENDAR_PHASE_CHANGED"):
            calendar.normalize(self.payload(self.instant,"MARKET_HOURS"),self.instant)
        body=self.payload(self.instant)
        body["sessions"][1]["exchange"]="NSE"
        with self.assertRaisesRegex(ValueError,"INVALID_CALENDAR_IDENTITY"):
            calendar.normalize(body,self.instant)

    def test_transition_preserves_retry_backoff(self):
        before=self.due("COMPANY_NEWS")
        with closing(research._connect()) as db,db:
            db.execute("UPDATE research_job_state SET status='FAILED' WHERE job='COMPANY_NEWS'")
        self.refresh(self.instant)
        self.assertEqual(self.due("COMPANY_NEWS"),before)
