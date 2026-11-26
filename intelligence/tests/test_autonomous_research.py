import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app import autonomous_research as research


class AutonomousResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"ATLAS_RESEARCH_SNAPSHOT_DB": self.temp.name + "/research.sqlite3",
            "ATLAS_AUTONOMOUS_RESEARCH_ENABLED": "true"})
        self.env.start()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.env.stop)

    def test_pending_then_persisted_sections(self):
        self.assertTrue(all(row["status"] == "PENDING" for row in research.read_snapshot()["sections"]))
        research.refresh_once(lambda exchange: {"eligible_count": 1, "exchange": exchange},
                              lambda category: {"category": category, "growth_outlook": []})
        snapshot = research.read_snapshot()
        self.assertEqual(len(snapshot["sections"]), 12)
        self.assertIn("CORPORATE_BOND",{row["section"] for row in snapshot["sections"]})
        self.assertTrue(all(row["status"] == "READY" for row in snapshot["sections"]))
        self.assertEqual(snapshot["sections"][0]["result"]["exchange"], "NSE")

    def test_fund_snapshot_persists_only_aggregate_qualification_counts(self):
        summary={"evaluated_count":2,"top_eligible_count":1,"growth_eligible_count":0,
                 "excluded":[{"identifier":"DO_NOT_PERSIST","top_performer_missing":["EXPENSE_RATIO","EXPENSE_RATIO"],
                              "growth_outlook_missing":["OFFICIAL_RISKOMETER","PRIVATE_MARKER"]},
                             {"identifier":"SECOND_PRIVATE_ID","top_performer_missing":[],
                              "growth_outlook_missing":["OFFICIAL_RISKOMETER"]}]}
        payload={key:None for key in ("category","coverage","top_performers","growth_outlook",
            "recommendation_status","blockers","notice","filters","historical_coverage")}
        payload["qualification_summary"]=summary
        with patch.object(research,"dashboard",return_value=payload):
            snapshot=research.fund_snapshot("LARGE_CAP")
        counts=snapshot["qualification_counts"]
        self.assertEqual(counts["evaluated_count"],2)
        self.assertEqual(counts["top_missing_gate_counts"],{"EXPENSE_RATIO":1})
        self.assertEqual(counts["growth_missing_gate_counts"],{"OFFICIAL_RISKOMETER":2,"UNKNOWN_GATE":1})
        self.assertNotIn("DO_NOT_PERSIST",str(snapshot))
        self.assertNotIn("PRIVATE_MARKER",str(snapshot))
        self.assertNotIn("qualification_summary",snapshot)
        summary["growth_eligible_count"]=1
        self.assertIsNone(research._fund_qualification_counts(summary))
        self.assertIsNone(research._fund_qualification_counts(None))
        self.assertEqual(research._fund_qualification_counts({"evaluated_count":0,"top_eligible_count":0,
            "growth_eligible_count":0,"excluded":[]})["top_missing_gate_counts"],{})

    def test_failure_retains_last_good_but_marks_failed(self):
        research.refresh_once(lambda exchange: {"exchange": exchange}, lambda category: {"category": category})
        def failed(exchange):
            raise RuntimeError("private-token-must-not-leak")
        research.refresh_once(failed, lambda category: {"category": category})
        sections = research.read_snapshot()["sections"]
        self.assertEqual(sections[0]["status"], "FAILED")
        self.assertEqual(sections[0]["result"]["exchange"], "NSE")
        self.assertNotIn("private-token", str(sections))
        self.assertEqual(sections[2]["status"], "READY")

    def test_market_only_read_skips_fund_payloads_and_matches_full_snapshot(self):
        instant=datetime(2026,11,26,4,tzinfo=timezone.utc)
        with patch.object(research,"now",return_value=instant):
            research.refresh_once(
                lambda exchange: {"exchange":exchange,"momentum_leaders":[{"as_of":"2026-11-25"}]},
                lambda category: {"category":category,"fund_only_payload":"x"*10000})
            # Measure decoded payload count, not machine-specific wall time.
            with patch.object(research.json,"loads",wraps=research.json.loads) as loads:
                market=research.read_market_snapshot()
                self.assertEqual(loads.call_count,2)
            with patch.object(research.json,"loads",wraps=research.json.loads) as loads:
                full=research.read_snapshot(False)
                self.assertEqual(loads.call_count,12)
            self.assertEqual(market,{**full,"sections":full["sections"][:2]})
            self.assertNotIn("fund_only_payload",str(market))
            # A corrupt fund section is still visible to the full reader but
            # is irrelevant to equity-only consumers.
            from contextlib import closing
            with closing(research._connect()) as db,db:
                db.execute("UPDATE research_sections SET payload='not-json' WHERE section='LARGE_CAP'")
            self.assertEqual(research.read_market_snapshot(),market)
            self.assertEqual(next(r for r in research.read_snapshot(False)["sections"] if r["section"]=="LARGE_CAP")["status"],"FAILED")
        with patch.object(research,"now",return_value=datetime(2026,11,30,4,tzinfo=timezone.utc)):
            self.assertTrue(all(r["status"]=="STALE" for r in research.read_market_snapshot()["sections"]))

    def test_equity_only_background_jobs_use_market_reader(self):
        snapshot={"enabled":True,"sections":[{"section":"NSE","status":"READY"}]}
        with patch.object(research,"read_market_snapshot",return_value=snapshot) as market, \
             patch.object(research,"read_snapshot",side_effect=AssertionError("full snapshot not needed")), \
             patch.object(research.automatic_company_evidence,"permitted",return_value=True), \
             patch.object(research.automatic_news,"permitted",return_value=True), \
             patch.object(research.automatic_company_evidence,"refresh") as company, \
             patch.object(research.automatic_news,"refresh") as news, \
             patch.object(research.automatic_strategy_validation,"refresh") as replay, \
             patch.object(research.watch_outcomes,"refresh") as outcomes:
            for job in ("COMPANY_EVIDENCE","COMPANY_NEWS","STRATEGY_REPLAY","WATCH_OUTCOMES"):
                self.assertEqual(research._execute_job(job),"PASS_COMPLETED")
            self.assertEqual(market.call_count,4)
            for consumer in (company,news,replay,outcomes):
                consumer.assert_called_once_with(snapshot,research._connect)

    def test_invalid_interval_disables_scheduler(self):
        with patch.dict(os.environ, {"ATLAS_AUTONOMOUS_RESEARCH_INTERVAL_SECONDS": "1"}):
            self.assertFalse(research.config()[0])

    def test_recent_snapshot_with_expired_observation_is_stale(self):
        before = datetime(2026, 11, 24, 18, 0, tzinfo=timezone.utc)
        after = datetime(2026, 11, 24, 19, 0, tzinfo=timezone.utc)
        with patch.object(research, "now", return_value=before):
            research.refresh_once(
                lambda exchange: {"momentum_leaders": [{"as_of": "2026-11-20"}]},
                lambda category: {"historical_coverage": {"comparison_date": "2026-11-17",
                    "items": [{"nav_date": "2026-11-17"}]}})
            self.assertTrue(all(r["status"] == "READY" for r in research.read_snapshot(False)["sections"]))
        with patch.object(research, "now", return_value=after):
            sections = research.read_snapshot(False)["sections"]
            self.assertTrue(all(r["status"] == "STALE" for r in sections))
            self.assertTrue(all(r["error_code"] == "UNDERLYING_OBSERVATION_STALE" for r in sections))
            self.assertTrue(all(r["result"] is not None for r in sections))

    def test_corrupt_section_does_not_break_other_sections(self):
        research.refresh_once(lambda exchange: {"exchange": exchange}, lambda category: {"category": category})
        from contextlib import closing
        with closing(research._connect()) as db, db:
            db.execute("UPDATE research_sections SET payload=? WHERE section='NSE'", ("not-json",))
        rows = research.read_snapshot(False)["sections"]
        self.assertEqual(rows[0]["status"], "FAILED")
        self.assertIsNone(rows[0]["result"])
        self.assertEqual(rows[0]["error_code"], "INVALID_STORED_RESEARCH_SNAPSHOT")
        self.assertTrue(all(r["status"] == "READY" for r in rows[1:]))

    def test_disabled_scheduler_does_not_label_old_results_ready(self):
        research.refresh_once(lambda exchange: {"exchange": exchange}, lambda category: {"category": category})
        with patch.dict(os.environ, {"ATLAS_AUTONOMOUS_RESEARCH_ENABLED": "false"}):
            self.assertTrue(all(r["status"] == "DISABLED" for r in research.read_snapshot(False)["sections"]))

    def test_expanded_discovery_uses_bounded_batches_and_existing_screener(self):
        from urllib.parse import parse_qs, urlsplit
        from datetime import date, timedelta
        instruments=[{"id":i,"exchange":"NSE","symbol":f"T{i}","active":True,
                      "listing_status":"ACTIVE","series":"EQ","instrument_type":"EQ",
                      "recent_registry_count":230} for i in range(1,201)]
        calls=[]
        def load(path):
            calls.append(path)
            if "discovery-universe?" in path:
                return instruments
            ids=[int(i) for i in parse_qs(urlsplit(path).query)["ids"]]
            self.assertLessEqual(len(ids),20)
            return [{"instrument_id":i,"trade_date":(date(2026,10,31)+timedelta(days=d)).isoformat(),
                     "open":100+d,"high":102+d,"low":99+d,"close":101+d,"volume":100000,
                     "adjustment_status":"RAW_UNADJUSTED"} for i in ids for d in range(24)]
        with patch.object(research,"now",return_value=datetime(2026,11,24,12,tzinfo=timezone.utc)), \
             patch.object(research,"backend_json",side_effect=load):
            result=research.market_snapshot("NSE")
        self.assertEqual(result["eligible_count"],200)
        self.assertEqual(result["company_research_universe"],[]) # missing exact ISINs never enter company rotation
        self.assertEqual(result["universe_size"],200)
        self.assertEqual(result["discovery_coverage"]["recent_registry_count"],230)
        self.assertEqual(len(calls),11)
        self.assertEqual(len(result["top_gainers"]),5)

    def test_session_coverage_is_distinct_from_usable_history_depth(self):
        from datetime import date,timedelta
        instruments=[{"id":i,"exchange":"NSE","symbol":f"T{i}","active":True,
                      "listing_status":"ACTIVE","series":"EQ","instrument_type":"EQ",
                      "recent_registry_count":4,"expected_session":"2026-11-23",
                      "expected_session_count":3} for i in range(1,4)]
        last=date(2026,11,23)
        candles=[{"instrument_id":i,"trade_date":(last-timedelta(days=n-1-d)).isoformat(),
                  "open":100+d,"high":102+d,"low":99+d,"close":101+d,"volume":100000,
                  "adjustment_status":"RAW_UNADJUSTED"}
                 for i,n in [(1,50),(2,100),(3,200)] for d in range(n)]
        with patch.object(research,"now",return_value=datetime(2026,11,24,12,tzinfo=timezone.utc)), \
             patch.object(research,"backend_json",side_effect=[instruments,candles]):
            result=research.market_snapshot("NSE")
        self.assertEqual(result["discovery_coverage"]["expected_session_count"],3)
        self.assertEqual(result["history_coverage"]["SWING"]["eligible_histories"],3)
        self.assertEqual(result["history_coverage"]["SHORT_TERM"]["eligible_histories"],2)
        self.assertEqual(result["history_coverage"]["LONG_TERM"]["eligible_histories"],1)

    def test_batch_rejects_unrequested_history(self):
        row={"id":1,"exchange":"NSE","symbol":"TEST","active":True,"listing_status":"ACTIVE",
             "series":"EQ","instrument_type":"EQ","recent_registry_count":1}
        with patch.object(research,"backend_json",side_effect=[[row],[{"instrument_id":2}]]):
            with self.assertRaisesRegex(ValueError,"IDENTITY_MISMATCH"):
                research.market_snapshot("NSE")

    def test_published_calendar_assertion_expires_at_ist_date_rollover(self):
        result={"discovery_coverage":{"expected_session":"2026-11-23","calendar_checked_on":"2026-11-24"},
                "top_gainers":[{"as_of":"2026-11-23"}]}
        from datetime import date
        self.assertTrue(research._published_evidence_current("NSE",result,date(2026,11,24)))
        self.assertFalse(research._published_evidence_current("NSE",result,date(2026,11,25)))
        result["top_gainers"][0]["as_of"]="2026-11-22"
        self.assertFalse(research._published_evidence_current("NSE",result,date(2026,11,24)))
