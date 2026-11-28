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

    def test_incremental_capture_uses_quarterly_source_timestamp_not_oldest_section(self):
        raw=report()
        raw["retrieved_at"]=(NOW-timedelta(hours=6)).isoformat()
        self.assertEqual(f.baseline(raw,NOW)["capture_at"],NOW.isoformat())
        raw["sections"]["quarterly_income"]["source"]["retrieved_at"]=(NOW+timedelta(minutes=1)).isoformat()
        self.assertIsNone(f.baseline(raw,NOW))
        raw["sections"]["quarterly_income"]["source"]["retrieved_at"]=(NOW-timedelta(hours=7)).isoformat()
        self.assertIsNone(f.baseline(raw,NOW))

    def test_due_publication_lookup_uses_original_maturity_and_excludes_malformed_rows(self):
        with tempfile.TemporaryDirectory() as d:
            def connect():
                db=sqlite3.connect(Path(d)/"test.db");db.row_factory=sqlite3.Row;return db
            e=f.baseline(report(),NOW)
            with connect() as db:
                f._table(db)
                db.execute("INSERT INTO earnings_persistence(isin,target_quarter,published_at,evidence) VALUES(?,?,?,?)",
                    (ISIN,e["target_quarter"],NOW.isoformat(),json.dumps(e)))
                db.execute("INSERT INTO earnings_persistence(isin,target_quarter,published_at,evidence) VALUES(?,?,?,?)",
                    ("INE009A01021",e["target_quarter"],NOW.isoformat(),json.dumps(e)))
            with patch.object(f.company,"permitted",return_value=True):
                self.assertEqual(f.due_identities(connect,NOW),[])
                self.assertEqual(f.due_identities(connect,datetime(2027,2,1,5,tzinfo=timezone.utc)),[ISIN])
                self.assertEqual(f.due_identities(connect,datetime(2027,8,1,5,tzinfo=timezone.utc)),[])
            with patch.object(f.company,"permitted",return_value=False):
                self.assertEqual(f.due_identities(connect,datetime(2027,2,1,5,tzinfo=timezone.utc)),[])

    def test_challengers_are_frozen_and_not_backfilled(self):
        evidence=f.baseline(report(),NOW)
        self.assertEqual(evidence["challengers"]["revenue"]["HALF_PERSISTENCE"]["amount_cr"],126)
        self.assertNotIn("DAMPED_ACCELERATION",evidence["challengers"]["revenue"])
        later=datetime(2027,2,1,5,tzinfo=timezone.utc)
        row={"isin":ISIN,"target_quarter":evidence["target_quarter"],"published_at":NOW.isoformat(),"evidence":json.dumps(evidence)}
        result=f.evaluate(row,report(later,True),later)
        self.assertEqual(result["metrics"]["revenue"]["challenger_absolute_errors_pp"]["HALF_PERSISTENCE"],7.5)
        evidence.pop("challenger_policy")
        row["evidence"]=json.dumps(evidence)
        self.assertNotIn("challenger_absolute_errors_pp",f.evaluate(row,report(later,True),later)["metrics"]["revenue"])


    def test_four_models_use_common_two_metric_cohort(self):
        import copy
        metric={"unchanged_absolute_error_pp":10,"persistence_absolute_error_pp":3,
                "challenger_absolute_errors_pp":{"HALF_PERSISTENCE":5,"DAMPED_ACCELERATION":2},
                "signed_errors_pp":{"UNCHANGED":10,"PERSISTENCE":-3,"HALF_PERSISTENCE":5,"DAMPED_ACCELERATION":-2}}
        rows=[{k:copy.deepcopy(metric) for k in f.METRICS} for _ in range(30)]
        result=f.matched_model_comparison(rows,35)
        self.assertEqual(result["status"],"MATCHED_FOUR_MODEL_DESCRIPTIVE_SAMPLE")
        self.assertEqual(result["models"][1]["metrics"]["revenue"]["mean_signed_error_pp"],-3)
        rows[-1]["net_profit"]["signed_errors_pp"].pop("DAMPED_ACCELERATION")
        self.assertEqual(f.matched_model_comparison(rows,35)["matched_count"],29)
        self.assertEqual(f.matched_model_comparison(rows,35)["status"],"INSUFFICIENT_COMMON_COHORT")
