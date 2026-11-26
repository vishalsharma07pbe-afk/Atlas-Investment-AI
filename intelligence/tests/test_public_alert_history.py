import tempfile,sqlite3,unittest
from pathlib import Path
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from app import public_alert_history as history,notifications,autonomous_research

class PublicAlertHistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"research.sqlite"
        self.now=datetime.now(timezone.utc)-timedelta(minutes=5)
        self.row={"id":"research-test-1","category":"RISK_WARNING","title":"TEST price-volume review",
            "description":"Recorded risk observation.","event_date":self.now.date().isoformat(),
            "published_at":self.now.isoformat(),"source_name":"ATLAS local price-volume research","source_url":None}

    def connect(self):
        db=sqlite3.connect(self.path)
        db.row_factory=sqlite3.Row
        return db

    def refresh(self,rows,instant=None):
        with patch("app.public_research_alerts.market_alerts",return_value=rows):
            history.refresh(self.connect,{"enabled":True},instant or self.now)

    def test_restart_duplicate_and_expiry(self):
        self.refresh([self.row])
        revision={**self.row,"description":"Newer description","published_at":(self.now+timedelta(minutes=1)).isoformat()}
        self.refresh([revision],self.now+timedelta(minutes=1))
        rows=history.read(self.connect,self.now+timedelta(minutes=2))
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0].description,self.row["description"])
        self.assertEqual(history.read(self.connect,self.now+timedelta(days=8)),[])
        self.refresh([],self.now+timedelta(days=8))
        with self.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM public_market_alert_history").fetchone()[0],0)

    def test_nonmarket_rejected_and_capacity_bounded(self):
        with self.assertRaises(ValueError):
            self.refresh([{**self.row,"category":"MARKET_EVENT"}])
        rows=[{**self.row,"id":f"research-test-{i}"} for i in range(120)]
        self.refresh(rows)
        self.assertEqual(len(history.read(self.connect,self.now)),history.LIMIT)

    def test_scheduler_persists_without_browser(self):
        with patch.object(autonomous_research,"_connect",self.connect),patch.object(autonomous_research,"read_snapshot",return_value={"enabled":True}),patch.object(autonomous_research,"now",return_value=self.now),patch("app.public_research_alerts.market_alerts",return_value=[self.row]):
            self.assertEqual(autonomous_research._execute_job("PUBLIC_RESEARCH_ALERTS"),"PASS_COMPLETED")
        self.assertEqual(len(history.read(self.connect,self.now)),1)

    def test_existing_feed_labels_historical_and_current_wins(self):
        self.refresh([self.row])
        with patch("app.notifications._load",return_value=[]),patch.object(autonomous_research,"config",return_value=(True,900)),patch.object(autonomous_research,"_connect",self.connect),patch.object(autonomous_research,"read_snapshot",return_value={"enabled":True}),patch("app.automatic_news.alerts",return_value=[]),patch("app.global_releases.alerts",return_value=[]),patch("app.economic_calendar.read",return_value={}),patch("app.public_research_alerts.market_alerts",return_value=[]) as market:
            old=notifications.details()
            self.assertEqual(old["alerts"][0]["research_state"],"HISTORICAL_OBSERVATION")
            self.assertEqual(notifications.summary()["revision_keys"],[self.row["id"]])
            market.return_value=[self.row]
            current=notifications.details()
            self.assertEqual(len(current["alerts"]),1)
            self.assertEqual(current["alerts"][0]["research_state"],"CURRENT_OBSERVATION")
            market.return_value=[]
            with patch("app.public_alert_history.read",side_effect=sqlite3.OperationalError("test")):
                self.assertEqual(notifications.summary()["research_history_status"],"UNAVAILABLE")
                self.assertEqual(notifications.details()["alerts"],[])
