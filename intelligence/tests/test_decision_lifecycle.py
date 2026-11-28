import unittest
from app import decision_lifecycle as l,decision_quality as q
class LifecycleTest(unittest.TestCase):
    def test_missing_is_not_adverse_and_routes_use_existing_jobs(self):
        isin="INE002A01018"
        previous={isin:{"state":"PRIORITY_RESEARCH","published_at":"2026-10-01T06:00:00+00:00","outcome_status":"PENDING"},
                  "INE467B01029":{"state":"PRIORITY_RESEARCH","published_at":"2026-10-01T06:00:00+00:00","outcome_status":"PENDING"}}
        row={"isin":isin,"exchange":"NSE","decision_quality":{"methodology":q.VERSION,"state":"EVIDENCE_INCOMPLETE",
             "missing_checks":["CURRENT_QUARTER_SCENARIO","REPORTED_EARNINGS_AND_EPS_GROWTH"],"adverse_findings":[]}}
        report={"status":"RESEARCH_AVAILABLE","stocks":[row],"funds":[]}
        result=l.attach(report,previous,{"jobs":[{"job":"COMPANY_EVIDENCE","status":"WAITING_EVIDENCE","next_due_at":"2026-11-28T14:00:00Z"}]})
        self.assertEqual(row["lifecycle"]["status"],"EVIDENCE_LOST_REVIEW")
        self.assertEqual(result["changes"],{"EVIDENCE_LOST_REVIEW":1})
        self.assertEqual(result["recovery"][0]["affected_candidates"],1)
        self.assertEqual(result["recovery"][0]["status"],"WAITING_EVIDENCE")
        self.assertNotIn("INE467B01029",str(result))
