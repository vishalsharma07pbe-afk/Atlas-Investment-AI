import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from app import data_readiness

NOW = datetime(2026,11,14,0,0,tzinfo=timezone.utc)

class DataReadinessTests(unittest.TestCase):
    def setUp(self):
        stub = patch.object(data_readiness, 'backend_json', return_value=None)
        stub.start()
        self.addCleanup(stub.stop)
    def test_missing_datasets_fail_closed_without_creating_files(self):
        with tempfile.TemporaryDirectory() as root:
            paths={key:lambda key=key:Path(root)/(key+".sqlite") for key in data_readiness.SOURCE_PATHS}
            with patch.dict(data_readiness.SOURCE_PATHS,paths):
                result=data_readiness.readiness(NOW)
                self.assertFalse(result["live_market_data_connected"])
                self.assertFalse(result["automatic_research_enabled"])
                self.assertTrue(all(d["status"]=="NOT_IMPORTED" for d in result["datasets"]))
                self.assertEqual(list(Path(root).iterdir()),[])

    def test_recent_stale_and_future_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            dbs={}
            for code,_,table,column,*_ in data_readiness.SOURCES:
                path=Path(root)/(code+".sqlite")
                dbs[code]=path
                with sqlite3.connect(path) as db:
                    db.execute(f"CREATE TABLE {table} ({column} TEXT)")
                    value={"MUTUAL_FUND_NAV":"2026-11-13",
                           "INSTITUTIONAL_FLOWS":"2026-10-01",
                           "GLOBAL_NEWS":"2026-11-15T00:00:00+00:00"}[code]
                    db.execute(f"INSERT INTO {table} VALUES (?)",(value,))
            with patch.dict(data_readiness.SOURCE_PATHS,{key:lambda key=key:dbs[key] for key in dbs}):
                result=data_readiness.readiness(NOW)
            self.assertEqual([d["status"] for d in result["datasets"]],
                ["RECENT_LOCAL_EVIDENCE","STALE_DATA","FUTURE_TIMESTAMP"])
            self.assertTrue(all(not d["usable_as_live_market_data"] for d in result["datasets"]))

    def test_corrupt_database_is_explicitly_unavailable(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"bad.sqlite"
            path.write_bytes(b"not a database")
            count, latest, issue=data_readiness._snapshot(path,"nav_schemes","nav_date")
            self.assertEqual((count,latest,issue),(0,None,"STORAGE_UNAVAILABLE"))

    def test_timezone_required(self):
        with self.assertRaisesRegex(ValueError,"timezone-aware"):
            data_readiness.readiness(datetime(2026,11,14))


    def test_stored_provider_evidence_does_not_imply_live_feed_or_qualified_recommendations(self):
        health={"scheduledFeedsEnabled":True,"officialAmfiNav":{"records":100,"latest":"2026-11-13"},
                "upstoxRegistry":{"records":10,"latest":"2026-11-13T12:00:00+00:00"},
                "upstoxDailyHistory":{"records":1000,"latest":"2026-11-12"}}
        with patch.dict("os.environ",{"ATLAS_AUTONOMOUS_RESEARCH_ENABLED":"true"}), \
             patch("app.autonomous_research.read_snapshot",return_value={"sections":[{"section":"NSE","status":"READY","generated_at":NOW.isoformat()}]}), \
             patch.object(data_readiness,"live_feed_observation",return_value=False):
            result=data_readiness.readiness(NOW,lambda _:health)
        self.assertTrue(result["automatic_research_enabled"])
        self.assertFalse(result["live_market_data_connected"])
        self.assertFalse(result["actionable_recommendations_enabled"])
        self.assertEqual(result["research_sections"][0]["status"],"READY")
        self.assertEqual([row["status"] for row in result["backend_evidence"]],["RECENT_LOCAL_EVIDENCE"]*3)

    def test_fresh_tick_not_configuration_is_required(self):
        from types import SimpleNamespace
        from app.upstox_quote_worker import quote_worker
        settings=SimpleNamespace(provider="UPSTOX",licensed_data_access=True,entitlement_confirmed=True)
        with patch.object(data_readiness,"settings",settings), \
             patch.object(quote_worker,"running",True),patch.object(quote_worker.cache,"connected",True), \
             patch.object(quote_worker,"active_keys",{"NSE_EQ|TEST"}), \
             patch.object(quote_worker.cache,"snapshot",return_value={"status":"STALE"}) as tick:
            self.assertFalse(data_readiness.live_feed_observation(NOW))
            tick.return_value={"status":"LIVE"}
            self.assertTrue(data_readiness.live_feed_observation(NOW))
            settings.entitlement_confirmed=False
            self.assertFalse(data_readiness.live_feed_observation(NOW))

if __name__=="__main__":
    unittest.main()
