import unittest,json,sqlite3,tempfile
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import patch
from app import forward_earnings as f
NOW=datetime(2026,11,27,5,tzinfo=timezone.utc)
ISIN="INE002A01018"
def report(now=NOW,later=False,revised=False):
    points=[("2025-09-30",100),("2025-12-31",120),("2026-09-30",110 if not revised else 115)]
    if later:points.append(("2026-12-31",135))
    return {"isin":ISIN,"retrieved_at":now.isoformat(),"sections":{"quarterly_income":{"status":"AVAILABLE",
        "source":{"provider":"UPSTOX","endpoint":f"/v2/fundamentals/{ISIN}/income-statement","retrieved_at":now.isoformat()},
        "data":{"statement_type":"consolidated","time_period":"quarterly","units":"crore","series":{
            k:[{"period":d,"value":v} for d,v in points] for k in f.METRICS}}}}}
class ForwardEarningsTest(unittest.TestCase):
    def test_freeze_before_target_and_compare_against_seasonal_baseline(self):
        e=f.baseline(report(),NOW)
        self.assertEqual(e["target_quarter"],"2026-12-31")
        self.assertEqual(e["metrics"]["revenue"]["persistence_amount_cr"],132)
        self.assertFalse(e["qualified"])
        later=datetime(2027,2,1,5,tzinfo=timezone.utc)
        row={"isin":ISIN,"target_quarter":e["target_quarter"],"published_at":NOW.isoformat(),"evidence":json.dumps(e)}
        outcome=f.evaluate(row,report(later,True),later)
        self.assertEqual(outcome["metrics"]["revenue"]["persistence_absolute_error_pp"],2.5)
        self.assertEqual(outcome["metrics"]["revenue"]["unchanged_absolute_error_pp"],12.5)
        self.assertEqual(f.evaluate(row,report(later,True,True),later)["status"],"REVISED_BASE_EVIDENCE")
        self.assertIsNone(f.baseline(report(later),later))
        self.assertIsNone(f.baseline(report(),NOW+timedelta(hours=25)))
    def test_immutable_and_private_scope(self):
        with tempfile.TemporaryDirectory() as d:
            def connect():
                db=sqlite3.connect(Path(d)/"test.db");db.row_factory=sqlite3.Row;return db
            item={"isin":ISIN,"exchange":"NSE","id":1,"symbol":"TEST","as_of":"2026-11-26"}
            snapshot={"enabled":True,"scope":"PUBLIC_MARKET_RESEARCH_ONLY","research_date":NOW.date().isoformat(),"sections":[{"section":"NSE","status":"READY",
                 "result":{"horizons":{"SWING":{"candidates":[item]}},"venue_observations":[dict(item)],
                    "discovery_coverage":{"calendar_checked_on":NOW.date().isoformat(),"calendar_status":"PUBLISHED_SESSION","expected_session":item["as_of"]}}}]}
            with patch.object(f.company,"permitted",return_value=True),patch.object(f.company,"cached_action_reports",return_value={ISIN:report()}) as loader:
                self.assertEqual(f.refresh(snapshot,connect,NOW),1)
                self.assertEqual(f.refresh(snapshot,connect,NOW),0)
                snapshot["research_date"]="2026-11-26"
                self.assertEqual(f.refresh(snapshot,connect,NOW),0)
                snapshot["research_date"]=NOW.date().isoformat()
                self.assertEqual(f.summary(connect,NOW)["pending_count"],1)
                with connect() as db:
                    with self.assertRaises(sqlite3.IntegrityError):db.execute("UPDATE earnings_persistence SET evidence='{}'")
                snapshot["scope"]="PRIVATE"
                loader.reset_mock()
                self.assertEqual(f.refresh(snapshot,connect,NOW),0)
                loader.assert_not_called()
