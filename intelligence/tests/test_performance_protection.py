import unittest,tempfile,sqlite3
from datetime import datetime,timedelta,timezone
from app import performance_protection as p

NOW=datetime(2026,11,28,6,tzinfo=timezone.utc)
def report(stock=None,fund=None):
    r={"status":"RESEARCH_AVAILABLE","stocks":[{"action":"RESEARCH_FOR_ENTRY"}],
       "funds":[{"category":"LARGE_CAP","items":[{"action":"COMPARE_FOR_SIP"}]},{"category":"MID_CAP","items":[{"action":"COMPARE_FOR_SIP"}]}],
       "decision_quality":{},"next_steps":[]}
    if stock:r["decision_outcomes"]={"states":{"PRIORITY_RESEARCH":{"status":stock}}}
    if fund:r["fund_decision_outcomes"]={"LARGE_CAP":{"states":{"PRIORITY_RESEARCH":{"tri_review_status":fund}}}}
    return r

class ProtectionTest(unittest.TestCase):
    def test_hold_survives_missing_and_releases_only_after_comparable_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            def connect():
                db=sqlite3.connect(tmp+"/watch.db");db.row_factory=sqlite3.Row;return db
            adverse=report("ADVERSE_OBSERVED_SAMPLE","ADVERSE_DESCRIPTIVE_SAMPLE")
            p.attach(adverse,connect)
            self.assertEqual(adverse["stocks"][0]["action"],"WATCH_FOR_CONFIRMATION")
            p.update(adverse,connect,NOW)
            missing=report()
            p.update(missing,connect,NOW+timedelta(days=1));p.attach(missing,connect)
            self.assertEqual(missing["performance_protection"]["held_scopes"],["STOCK","LARGE_CAP"])
            self.assertEqual(missing["funds"][0]["items"][0]["action"],"WATCH_FOR_CONFIRMATION")
            self.assertEqual(missing["funds"][1]["items"][0]["action"],"COMPARE_FOR_SIP")
            positive=report("POSITIVE_DESCRIPTIVE_SAMPLE","POSITIVE_DESCRIPTIVE_SAMPLE")
            p.attach(positive,connect)
            self.assertEqual(positive["performance_protection"]["held_scopes"],["STOCK","LARGE_CAP"])
            p.update(report("POSITIVE_DESCRIPTIVE_SAMPLE","POSITIVE_DESCRIPTIVE_SAMPLE"),connect,NOW+timedelta(days=2))
            p.update(report("ADVERSE_OBSERVED_SAMPLE"),connect,NOW)
            fresh=report();p.attach(fresh,connect)
            self.assertEqual(fresh["performance_protection"]["held_scopes"],[])
    def test_truncated_sample_does_not_release(self):
        r=report("POSITIVE_DESCRIPTIVE_SAMPLE")
        r["decision_outcomes"]["truncated"]=True
        self.assertNotIn("STOCK",p.observations(r))
