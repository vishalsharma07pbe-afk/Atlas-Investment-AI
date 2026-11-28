import tempfile,sqlite3,unittest
from datetime import date,datetime,timedelta,timezone
from app import action_effectiveness as a,decision_quality as q

TODAY=date(2026,11,28)
def pair(day,advantage=5,missing=False):
    return [{"day":day,"identity":"INE002A01018","group":"NSE","arm":"CONDITIONAL","endpoints":("a","b",40),
             "net":10+advantage,"stress":9+advantage,"benchmark":8},
            {"day":day,"identity":"INE467B01029","group":"NSE","arm":"WITHHELD","endpoints":None if missing else ("a","b",40),
             "net":None if missing else 10,"stress":None if missing else 9,"benchmark":None if missing else 8}]
class ActionEffectivenessTest(unittest.TestCase):
    def test_overlap_and_failed_first_date_not_replaced(self):
        rows=pair(TODAY,missing=True)+pair(TODAY+timedelta(days=1))+pair(TODAY+timedelta(days=68))+pair(TODAY+timedelta(days=136))
        result=a.summarize(rows,60)
        self.assertEqual(result["matched_dates"]["eligible_dates"],4)
        self.assertEqual(result["matched_dates"]["observed_dates"],3)
        self.assertEqual(result["nonoverlapping_dates"]["eligible_dates"],3)
        self.assertEqual(result["nonoverlapping_dates"]["observed_dates"],2)
        self.assertEqual(result["status"],"INSUFFICIENT_MATCHED_ACTION_EVIDENCE")
        self.assertEqual(result["arms"]["WITHHELD"]["coverage_percent"],75)
    def test_descriptive_only_and_matched_endpoints(self):
        rows=sum([pair(TODAY+timedelta(days=68*i)) for i in range(3)],[])
        result=a.summarize(rows,60)
        self.assertEqual(result["status"],"DESCRIPTIVE_NONOVERLAPPING_COMPARISON")
        self.assertFalse(result["qualified"])
        self.assertEqual(result["nonoverlapping_dates"]["median_net_advantage_pp"],5)
        self.assertEqual(a.summarize(rows,60,truncated=True)["status"],"INSUFFICIENT_MATCHED_ACTION_EVIDENCE")
        rows[-1]["endpoints"]=("a","c",41)
        self.assertEqual(a.summarize(rows,60)["nonoverlapping_dates"]["observed_dates"],2)
    def test_daily_no_action_immutable_and_private_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            def connect():
                db=sqlite3.connect(tmp+"/audit.db");db.row_factory=sqlite3.Row;return db
            instant=datetime(2026,11,28,5,tzinfo=timezone.utc)
            snapshot={"enabled":True,"scope":"PUBLIC_MARKET_RESEARCH_ONLY","research_date":TODAY.isoformat(),
                      "investment_analyst":{"status":"NO_SUPPORTED_CANDIDATES","research_date":TODAY.isoformat()}}
            self.assertTrue(a.capture(snapshot,connect,instant))
            r=snapshot["investment_analyst"];r.update(status="RESEARCH_AVAILABLE",decision_quality={"methodology":q.VERSION},
                stocks=[{"qualified":False,"action":"RESEARCH_FOR_ENTRY","decision_quality":{"methodology":q.VERSION,"qualified":False,"state":"PRIORITY_RESEARCH"}}])
            self.assertFalse(a.capture(snapshot,connect,instant+timedelta(hours=1)))
            summary=a.daily_summary(connect,TODAY)
            self.assertEqual(summary["observed_days"],1)
            self.assertEqual(summary["scopes"]["STOCK"]["days_with_conditional_action"],0)
            snapshot["scope"]="PRIVATE"
            self.assertFalse(a.capture(snapshot,lambda:self.fail("private DB access"),instant))
            with connect() as db:
                with self.assertRaises(sqlite3.IntegrityError):db.execute("UPDATE final_action_day SET evidence='{}'")
