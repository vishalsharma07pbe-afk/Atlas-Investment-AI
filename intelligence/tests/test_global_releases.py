import os
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from app import global_releases as releases, autonomous_research as research, notifications

NOW=datetime(2026,11,25,12,tzinfo=timezone.utc)
def rss(host="www.federalreserve.gov"):
    return (f'<rss version="2.0"><channel><title>Feed</title>'
            f'<item><title>Federal Reserve monetary policy statement</title><link>https://{host}/news/a.htm</link>'
            '<pubDate>Tue, 24 Nov 2026 12:00:00 GMT</pubDate></item>'
            '</channel></rss>').encode()

class GlobalReleaseTests(unittest.TestCase):
    def setUp(self):
        root=tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        env=patch.dict(os.environ,{"ATLAS_RESEARCH_SNAPSHOT_DB":root.name+"/research.sqlite",
            "MARKET_DATA_USAGE_RIGHTS_CONFIRMED":"true","ATLAS_GLOBAL_RELEASES_SOURCES":"FED,BLS_CPI",
            "ATLAS_AUTONOMOUS_RESEARCH_ENABLED":"true"})
        env.start()
        self.addCleanup(env.stop)
    def test_official_publication_and_independent_sources(self):
        rows=releases.normalize(rss(),"FED",NOW)
        self.assertEqual(rows[0]["topics"],["MONETARY_POLICY"])
        releases.refresh(research._connect,"FED",NOW,lambda *_:rows)
        report=releases.read(research._connect,NOW)
        self.assertEqual(report["status"],"PARTIAL")
        self.assertEqual(len(report["events"]),1)
        self.assertEqual(report["sources"][2]["status"],"AWAITING_EVIDENCE")
        self.assertEqual(releases.alerts(research._connect,NOW)[0]["category"],"MARKET_EVENT")
        self.assertEqual(releases.read(research._connect,NOW+timedelta(hours=3))["events"],[])
    def test_malformed_future_and_foreign_links(self):
        for raw in (rss("example.com"),rss().replace(b"24 Nov",b"26 Nov"),
                    rss().replace(b" GMT",b""),b"<!DOCTYPE rss>"+rss(),
                    rss().replace(b"https://",b"https://fake@")):
            with self.assertRaises(ValueError):
                releases.normalize(raw,"FED",NOW)
        with self.assertRaises(ValueError):
            releases.normalize(b"<html/>","FED",NOW)
    def test_per_source_permission(self):
        self.assertFalse(releases.permitted("ECB"))
        self.assertEqual(research._execute_job("RELEASE_ECB"),"DISABLED_OR_NOT_AUTHORIZED")
    def test_notifications_do_not_depend_on_company_feed_permission(self):
        rows=releases.normalize(rss(),"FED",NOW)
        releases.refresh(research._connect,"FED",NOW,lambda *_:rows)
        with patch.object(notifications,"_load",return_value=[]), \
             patch("app.automatic_news.alerts",return_value=[]), \
             patch.object(releases,"alerts",return_value=releases.alerts(research._connect,NOW)):
            result=notifications.summary()
        self.assertIn("global-release-"+rows[0]["id"],result["ids"])
