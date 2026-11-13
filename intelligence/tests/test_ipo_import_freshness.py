import unittest
from datetime import datetime,timedelta,timezone
from app.ipo_operations import _import_freshness

class ImportFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,13,12,tzinfo=timezone.utc)
    def record(self,mode,hours):
        return {"outcome":"SUCCESS","mode":mode,
            "attempted_at":(self.now-timedelta(hours=hours)).isoformat()}
    def test_missing_apply_dry_run_does_not_count(self):
        result=_import_freshness([self.record("DRY_RUN",1)],self.now)
        self.assertEqual(result["status"],"NO_SUCCESSFUL_IMPORT")
        self.assertIsNone(result["last_successful_apply_at"])
        self.assertIsNotNone(result["last_successful_dry_run_at"])
    def test_recent_apply(self):
        result=_import_freshness([self.record("APPLY",3)],self.now)
        self.assertEqual(result["status"],"RECENT_IMPORT")
        self.assertEqual(result["hours_since_successful_apply"],3)
    def test_stale_apply_not_masked_by_dry_run(self):
        result=_import_freshness([self.record("DRY_RUN",1),self.record("APPLY",30)],self.now)
        self.assertEqual(result["status"],"IMPORT_STALE")
    def test_failed_and_future_records_do_not_count(self):
        entries=[self.record("APPLY",-2),{"outcome":"FAILED","mode":"APPLY",
            "attempted_at":self.now.isoformat()}]
        self.assertEqual(_import_freshness(entries,self.now)["status"],"NO_SUCCESSFUL_IMPORT")
if __name__=="__main__":unittest.main()
