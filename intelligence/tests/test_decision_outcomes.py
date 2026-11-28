import json,sqlite3,tempfile,unittest
from datetime import datetime,date,timezone,timedelta
from unittest.mock import patch
from app import decision_outcomes as d,decision_quality as q

class DecisionOutcomeTest(unittest.TestCase):
    def test_no_rewrite_or_duplicate_publication(self):
        with tempfile.TemporaryDirectory() as folder:
            def connect():
                db=sqlite3.connect(folder+"/watch.db");db.row_factory=sqlite3.Row;return db
            instant=datetime(2026,11,28,6,tzinfo=timezone.utc)
            item={"id":1,"isin":"INE002A01018","symbol":"TEST","exchange":"NSE","tier":"ADJUSTED_JOINT",
                  "as_of":"2026-11-27","close":100,"qualified":False,
                  "decision_quality":{"methodology":q.VERSION,"state":"EVIDENCE_INCOMPLETE","qualified":False}}
            report={"research_date":"2026-11-28","status":"RESEARCH_AVAILABLE","stocks":[item],"decision_quality":{"methodology":q.VERSION}}
            self.assertEqual(d.publish(report,connect,instant),1)
            item["decision_quality"]["state"]="PRIORITY_RESEARCH"
            self.assertEqual(d.publish(report,connect,instant),0)
            self.assertEqual(d.summary(connect,instant)["states"]["EVIDENCE_INCOMPLETE"]["published"],1)
            self.assertEqual(d.summary(connect,instant)["states"]["PRIORITY_RESEARCH"]["published"],0)

    def test_adverse_sample_requires_maturity_coverage_and_distinct_companies(self):
        today=date(2026,11,28)
        rows=[]
        for i in range(30):
            published=today-timedelta(days=100+i)
            e={"methodology":d.VERSION,"decision_policy":q.VERSION,"decision_state":"PRIORITY_RESEARCH","isin":"INE"+str(i).zfill(9)}
            rows.append({"evidence":json.dumps(e),"published_at":published.isoformat()+"T00:00:00+00:00",
                         "maturity_date":(published+timedelta(days=60)).isoformat()})
        with patch.object(d.rel,"_outcome",return_value=.02),patch.object(d.rel,"_index_change",return_value=.05):
            result=d.summarize_rows(rows,today)["states"]["PRIORITY_RESEARCH"]
            self.assertEqual(result["status"],"ADVERSE_OBSERVED_SAMPLE")
            self.assertEqual(result["observed"],30)
            self.assertEqual(d.summarize_rows(rows[:29],today)["states"]["PRIORITY_RESEARCH"]["status"],"INSUFFICIENT_MATURE_COMPARABLE_EVIDENCE")
            self.assertEqual(d.summarize_rows(rows,today,True)["states"]["PRIORITY_RESEARCH"]["status"],"INSUFFICIENT_MATURE_COMPARABLE_EVIDENCE")
