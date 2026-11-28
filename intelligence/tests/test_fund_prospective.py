import unittest,tempfile,sqlite3,json
from datetime import date,datetime,timedelta,timezone
from app import fund_prospective as f
TODAY=date(2026,11,27)
NOW=datetime(2026,11,27,10,tzinfo=timezone.utc)
def snap():
    return {"enabled":True,"scope":"PUBLIC_MARKET_RESEARCH_ONLY","sections":[{"section":"LARGE_CAP","status":"READY","result":{"filters":{"horizon_months":60,"risk_tolerance":"MODERATE"},"historical_research_shortlist":{"methodology":"MF-MATCHED-PEER-1","category":"LARGE_CAP","status":"HISTORICAL_SHORTLIST_AVAILABLE","matched_count":5,"last_date":"2026-11-26","date_digest":"a"*64,"items":[{"identifier":"123456","isin_growth":"INF179K01BB2","nav":"100","nav_date":"2026-11-26","score":75,"status":"HISTORICAL_RESEARCH_ONLY","qualified":False}]}}}]}
class ProspectiveTests(unittest.TestCase):
    def test_freeze_and_independent_mature_outcome(self):
        with tempfile.TemporaryDirectory() as tmp:
            def connect():
                db=sqlite3.connect(tmp+"/fund.sqlite");db.row_factory=sqlite3.Row;return db
            s=snap();self.assertEqual(f.publish(s,NOW,connect),1)
            s["sections"][0]["result"]["historical_research_shortlist"]["items"][0]["score"]=99
            self.assertEqual(f.publish(s,NOW,connect),0)
            with connect() as db:
                row=dict(db.execute("SELECT * FROM mf_prospective_watch").fetchone())
            self.assertEqual(json.loads(row["evidence"])["score"],75)
            later=NOW+timedelta(days=100);day=later.date()
            first=date(2026,11,26);maturity=TODAY+timedelta(days=90)
            points=[{"nav_date":(first+timedelta(days=i)).isoformat(),"nav":100+i*.1,"source_code":"AMFI"} for i in range((maturity-first).days+8)]
            payload={"status":"LOCAL_AMFI_OBSERVATIONS","identity":{"scheme_code":123456,"isin_growth":"INF179K01BB2","amfi_plan":"DIRECT","amfi_option":"GROWTH","category":"Open Ended Schemes(Equity Scheme - Large Cap Fund)","amfi_metadata_date":day.isoformat()},"rows":points}
            self.assertIsNotNone(f.evaluate(row,payload,day))
            f.refresh({"enabled":True,"scope":"PUBLIC_MARKET_RESEARCH_ONLY","sections":[]},later,connect,lambda _:payload)
            summary=f.summary("LARGE_CAP",day,connect)
            self.assertEqual(summary["bands"][1]["observed_count"],1)
            self.assertFalse(summary["calibrated"])
            with connect() as db:
                with self.assertRaises(sqlite3.IntegrityError):db.execute("UPDATE mf_prospective_watch SET outcome='{}'")
            points[0]["nav"]=101
            self.assertIsNone(f.evaluate(row,payload,day))
    def test_private_scope_not_published(self):
        s=snap();s["scope"]="PRIVATE"
        self.assertEqual(f.publish(s,NOW,lambda: self.fail("private scope must not access db")),0)

    def test_final_fund_decision_frozen_only_on_original_publication(self):
        from app import decision_quality as q
        with tempfile.TemporaryDirectory() as tmp:
            def connect():
                db=sqlite3.connect(tmp+"/fund.sqlite");db.row_factory=sqlite3.Row;return db
            item={"identifier":"123456","nav_date":"2026-11-26","qualified":False,
                  "decision_quality":{"methodology":q.VERSION,"qualified":False,"state":"EVIDENCE_INCOMPLETE"}}
            report={"research_date":TODAY.isoformat(),"status":"RESEARCH_AVAILABLE",
                "decision_quality":{"methodology":q.VERSION},"funds":[{"category":"LARGE_CAP","items":[item]}]}
            self.assertEqual(f.publish(snap(),NOW,connect,final_report=report),1)
            item["decision_quality"]["state"]="PRIORITY_RESEARCH"
            self.assertEqual(f.publish(snap(),NOW,connect,final_report=report),0)
            states=f.summary("LARGE_CAP",TODAY,connect)["decision_states"]
            self.assertEqual(states["EVIDENCE_INCOMPLETE"]["published"],1)
            self.assertEqual(states["PRIORITY_RESEARCH"]["published"],0)
