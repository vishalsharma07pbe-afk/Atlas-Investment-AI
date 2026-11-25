import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
import sqlite3
from unittest.mock import patch
from app import watch_outcomes as watch, autonomous_research as research

class WatchOutcomeTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        env=patch.dict(os.environ,{"ATLAS_RESEARCH_SNAPSHOT_DB":temp.name+"/research.sqlite3"})
        env.start()
        self.addCleanup(env.stop)
        self.instant=datetime(2026,11,24,10,tzinfo=timezone.utc)
        self.item={"id":7,"symbol":"TEST","exchange":"NSE","as_of":"2026-11-23","close":100,"adjustment_status":"ADJUSTED"}
        self.snapshot={"enabled":True,"sections":[{"section":"NSE","status":"READY","result":{"horizons":{"SWING":{"methodology":"TEST","candidates":[self.item]}}}}]}

    def test_publication_is_immutable_and_no_lookahead(self):
        watch.refresh(self.snapshot,research._connect,lambda _:self.fail("not mature"),self.instant)
        self.item["close"]=999
        watch.publish(self.snapshot,research._connect,self.instant+timedelta(days=1))
        rows=watch.summary(research._connect,"SWING")
        self.assertEqual(rows["counts"],{"PENDING":1})
        self.assertEqual(rows["items"][0]["published_at"],self.instant.isoformat())

    def test_mature_outcome_requires_adjusted_provider_history(self):
        self.item["isin"]="INE002A01018"
        watch.publish(self.snapshot,research._connect,self.instant)
        with research._connect() as db:
            row=db.execute("SELECT * FROM watch_outcomes").fetchone()
        points=[{"trade_date":(date(2026,11,24)+timedelta(days=i)).isoformat(),"close":100+i,
                 "open":100+i,"high":101+i,"low":99+i,"volume":10000,"revision":1,
                 "source_code":"TEST_PROVIDER","adjustment_status":"ADJUSTED","quality_status":"PROVIDER_VALIDATED"} for i in range(16)]
        payload={"instrument":{"id":7,"symbol":"TEST","exchange":"NSE","isin":self.item["isin"]},"candles":points}
        today=date(2026,12,10)
        calendar={"exchange":"NSE","through":"2026-12-09","days":[{"trade_date":p["trade_date"],"state":"REGULAR"} for p in points]}
        status,result=watch.evaluate(row,payload,today,calendar)
        self.assertEqual(status,"OBSERVED")
        self.assertEqual(result["entry_date"],"2026-11-25")
        self.assertEqual(result["exit_date"],"2026-12-08")
        self.assertEqual(result["evidence_version"],watch.OUTCOME_EVIDENCE_VERSION)
        self.assertEqual(result["observations"],14)
        self.assertEqual(watch.evaluate(row,{**payload,"candles":points[:1]+points[2:]},today,calendar),("EVIDENCE_GAP",None))
        self.assertEqual(watch.evaluate(row,{**payload,"candles":points[:14]+points[15:]},today,calendar),("EVIDENCE_GAP",None))
        self.assertEqual(watch.evaluate(row,payload,today,None),("CALENDAR_EVIDENCE_GAP",None))
        changed={**calendar,"days":[{**p,"state":"UNKNOWN"} if i==3 else p for i,p in enumerate(calendar["days"])]}
        self.assertEqual(watch.evaluate(row,payload,today,changed),("CALENDAR_EVIDENCE_GAP",None))
        points[5]["adjustment_status"]="RAW_UNADJUSTED"
        self.assertEqual(watch.evaluate(row,payload,today,calendar),("EVIDENCE_GAP",None))

    def test_publication_records_isin_and_rejects_identity_change(self):
        self.item["isin"]="INE002A01018"
        watch.publish(self.snapshot,research._connect,self.instant)
        with research._connect() as db:
            row=db.execute("SELECT * FROM watch_outcomes").fetchone()
        import json
        self.assertEqual(json.loads(row["evidence"])["isin"],"INE002A01018")
        payload={"instrument":{"id":7,"symbol":"TEST","exchange":"NSE","isin":"INE009A01021"},"candles":[]}
        self.assertEqual(watch.evaluate(row,payload,date(2026,12,10)),("IDENTITY_MISMATCH",None))

    def test_failed_snapshot_never_publishes(self):
        self.snapshot["sections"][0]["status"]="FAILED"
        watch.publish(self.snapshot,research._connect,self.instant)
        self.assertEqual(watch.summary(research._connect,"SWING")["items"],[])

    def test_ledger_rejects_mutations_to_publication_and_observed_outcome(self):
        watch.publish(self.snapshot,research._connect,self.instant)
        with research._connect() as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE watch_outcomes SET evidence='{}'")
            db.execute("UPDATE watch_outcomes SET status='OBSERVED',outcome='{}'")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE watch_outcomes SET status='PENDING'")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE watch_outcomes SET outcome=NULL")
