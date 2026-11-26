import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from app import research_alerts,notifications,economic_calendar

class ResearchAlertsTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime.now(timezone.utc)
        today=self.now.astimezone(research_alerts.IST).date()
        self.day=(today-timedelta(days=1)).isoformat()
        self.prior=(today-timedelta(days=2)).isoformat()
        row={"exchange":"NSE","id":1,"symbol":"TEST","isin":"INE009A01021","as_of":self.day}
        pressure={**row,"price_volume_pressure":{"status":"OBSERVED_PRICE_VOLUME_ONLY","as_of":self.day,
             "adjustment_status":"ADJUSTED","calendar_status":"LATEST_SESSION_MATCHED_ONLY","relative_volume":3,
             "change_percent":-4,"findings":["HIGH_VOLUME_DECLINE_REVIEW","HIGH_VOLUME_UPSIDE_REJECTION_REVIEW"]}}
        breakout={**row,"followthrough":{"status":"OBSERVED_FOLLOWTHROUGH","as_of":self.day,"adjustment_status":"ADJUSTED",
             "events":[{"direction":"UPSIDE","status":"REENTRY_OBSERVED","signal_date":self.prior,"reentry_date":self.day}]}}
        self.section={"section":"NSE","status":"READY","generated_at":(self.now-timedelta(minutes=5)).isoformat(),
            "result":{"discovery_coverage":{"calendar_status":"PUBLISHED_SESSION","calendar_checked_on":today.isoformat(),"expected_session":self.day},
            "price_volume_review":{"downside_items":[pressure]},"breakout_review":{"items":[breakout]}}}
        self.snapshot={"enabled":True,"sections":[self.section]}

    def test_market_alerts_use_existing_dated_adjusted_observations(self):
        rows=research_alerts.market_alerts(self.snapshot,self.now)
        self.assertEqual(len(rows),2)
        self.assertTrue(all(row["source_url"] is None for row in rows))
        self.assertTrue(all(row["category"]=="RISK_WARNING" for row in rows))
        a=[notifications.ResearchAlert.model_validate(row) for row in rows]
        self.section["generated_at"]=self.now.isoformat()
        b=[notifications.ResearchAlert.model_validate(row) for row in research_alerts.market_alerts(self.snapshot,self.now)]
        self.assertEqual([notifications._revision(x) for x in a],[notifications._revision(x) for x in b])
        self.section["status"]="STALE"
        self.assertEqual(research_alerts.market_alerts(self.snapshot,self.now),[])

    def test_withholds_unidentified_raw_or_older_events(self):
        self.section["result"]["price_volume_review"]["downside_items"][0]["price_volume_pressure"]["adjustment_status"]="RAW_UNADJUSTED"
        self.section["result"]["breakout_review"]["items"][0]["followthrough"]["events"][0]["reentry_date"]=self.prior
        self.assertEqual(research_alerts.market_alerts(self.snapshot,self.now),[])

    def test_calendar_reminder_is_bounded_and_schedule_revision_is_distinct(self):
        calendar={"status":"CURRENT_SCHEDULE","source_url":economic_calendar.SOURCE_PAGE,"retrieved_at":self.now.isoformat(),
            "events":[{"id":"a"*40,"headline":"Consumer Price Index","status":"SCHEDULED","review_window":True,
             "scheduled_at":(self.now+timedelta(hours=4)).isoformat()}]}
        first=research_alerts.calendar_alerts(calendar,self.now)
        self.assertEqual(len(first),1)
        self.assertEqual(first[0]["source_url"],economic_calendar.SOURCE_PAGE)
        calendar["events"][0]["scheduled_at"]=(self.now+timedelta(hours=5)).isoformat()
        self.assertNotEqual(first[0]["id"],research_alerts.calendar_alerts(calendar,self.now)[0]["id"])
        self.assertEqual(research_alerts.calendar_alerts(calendar,self.now+timedelta(hours=6)),[])

    def test_imported_alert_cannot_drop_source_url(self):
        row=research_alerts.market_alerts(self.snapshot,self.now)[0]
        with self.assertRaises(ValueError):
            notifications.Alert.model_validate(row)

    def test_existing_feed_includes_internal_reminders_without_fake_links(self):
        rows=research_alerts.market_alerts(self.snapshot,self.now)
        with patch("app.notifications._load",return_value=[]),patch("app.autonomous_research.config",return_value=(True,900)),patch("app.autonomous_research.read_snapshot",return_value=self.snapshot),patch("app.automatic_news.alerts",return_value=[]),patch("app.global_releases.alerts",return_value=[]),patch("app.research_alerts.market_alerts",return_value=rows),patch("app.economic_calendar.read",return_value={}):
            badge=notifications.summary()
            feed=notifications.details()
            self.assertEqual(badge["total"],2)
            self.assertNotIn("alerts",badge)
            self.assertEqual(set(badge["revision_keys"]),{r["id"] for r in rows})
            self.assertTrue(all(a["publication_basis"]=="RESEARCH_SNAPSHOT" and a["source_url"] is None for a in feed["alerts"]))
