import os
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from app import automatic_news as news, autonomous_research as research, notifications, p1_research

class AutomaticNewsTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        env=patch.dict(os.environ,{"ATLAS_RESEARCH_SNAPSHOT_DB":temp.name+"/research.sqlite",
            "ATLAS_ALERTS_FILE":temp.name+"/missing.json",
            "ATLAS_AUTONOMOUS_RESEARCH_ENABLED":"true","ATLAS_AUTOMATIC_NEWS_ENABLED":"true",
            "MARKET_DATA_USAGE_RIGHTS_CONFIRMED":"true","MARKET_DATA_ENTITLEMENT_CONFIRMED":"true",
            "UPSTOX_ACCESS_TOKEN":"test-only"})
        env.start()
        self.addCleanup(env.stop)
        self.now=datetime.now(timezone.utc).replace(microsecond=0)
        self.key="NSE_EQ|INE002A01018"
        self.item={"isin":"INE002A01018","symbol":"TEST","exchange":"NSE"}
        self.snapshot={"enabled":True,"sections":[{"section":"NSE","status":"READY",
            "result":{"horizons":{"SWING":{"candidates":[self.item]}}}}]}

    def report(self,keys,page_size):
        self.assertEqual(keys,[self.key])
        row={"instrument_key":self.key,"headline":"Company announces quarterly results",
             "url":"https://example.org/report","published_at":(self.now-timedelta(hours=1)).isoformat(),
             "source_provider":"UPSTOX_NEWS","summary":"private-unexpected-field"}
        return {"returned_keys":keys,"articles":[row,row,{**row,"url":"https://localhost/private"},
            {**row,"published_at":(self.now+timedelta(hours=1)).isoformat()},
            {**row,"instrument_key":"NSE_EQ|OTHER"}]}

    def test_deduplication_cached_card_and_existing_bell(self):
        news.refresh(self.snapshot,research._connect,self.report,self.now)
        news.refresh(self.snapshot,research._connect,lambda *a,**k:self.fail("duplicate request"),self.now)
        result=news.attach(self.snapshot,research._connect,self.now)
        articles=self.item["news_evidence"]["articles"]
        self.assertEqual(len(articles),1)
        self.assertEqual(articles[0]["topics"],["EARNINGS"])
        self.assertEqual(articles[0]["sentiment"],"NOT_ANALYZED")
        self.assertNotIn("private-unexpected-field",str(result))
        self.assertEqual(len(result["recent_company_news"]),1)
        self.assertEqual(notifications.summary()["total"],1)
        self.assertEqual(notifications.details()["alerts"][0]["category"],"MARKET_EVENT")
        self.assertEqual(news.alerts(research._connect,self.now+timedelta(hours=3)),[])

    def test_missing_key_is_not_empty_success_and_failure_suppresses(self):
        news.refresh(self.snapshot,research._connect,self.report,self.now)
        later=self.now+timedelta(hours=1)
        news.refresh(self.snapshot,research._connect,lambda *a,**k:{"returned_keys":[],"articles":[]},later)
        self.assertEqual(news.read(research._connect,later)[self.key]["status"],"UNAVAILABLE")
        self.assertEqual(news.alerts(research._connect,later),[])

    def test_permission_and_snapshot_gates(self):
        with patch.dict(os.environ,{"MARKET_DATA_USAGE_RIGHTS_CONFIRMED":"false"}):
            news.refresh(self.snapshot,research._connect,lambda *a,**k:self.fail("unauthorized"),self.now)
        self.snapshot["sections"][0]["status"]="FAILED"
        news.refresh(self.snapshot,research._connect,lambda *a,**k:self.fail("failed snapshot"),self.now)

    def test_adapter_preserves_multi_instrument_association(self):
        other="NSE_EQ|INE009A01021"
        row={"heading":"Company results released","article_link":"https://example.org/a",
            "published_time":int(self.now.timestamp()*1000)}
        with patch.object(p1_research,"_get",return_value={self.key:[row,row],other:[row],"NSE_EQ|UNKNOWN":[row]}):
            result=p1_research.company_news([self.key,other])
        self.assertEqual(result["count"],2)
        self.assertEqual(set(result["returned_keys"]),{self.key,other})

    def test_exact_isin_headline_shared_across_public_venues(self):
        from zoneinfo import ZoneInfo
        today=self.now.astimezone(ZoneInfo("Asia/Kolkata")).date()
        as_of=(today-timedelta(days=1)).isoformat()
        self.item.update(id=1,as_of=as_of)
        b={**self.item,"id":2,"exchange":"BSE"}
        data={"enabled":True,"scope":"PUBLIC_MARKET_RESEARCH_ONLY","research_date":today.isoformat(),"sections":[]}
        for row in (self.item,b):
            data["sections"].append({"section":row["exchange"],"status":"READY","result":{
                "discovery_coverage":{"calendar_checked_on":today.isoformat(),"calendar_status":"PUBLISHED_SESSION","expected_session":as_of},
                "horizons":{"SWING":{"status":"TECHNICAL_WATCH_ONLY","candidates":[row]}}}})
        news.refresh(data,research._connect,self.report,self.now)
        news.attach(data,research._connect,self.now)
        self.assertEqual(b["news_evidence"]["source_exchange"],"NSE")
        self.assertEqual(b["news_evidence"]["isin"],b["isin"])
        self.assertEqual(b["news_evidence"],self.item["news_evidence"])
        self.assertEqual(len(data["recent_company_news"]),1)
