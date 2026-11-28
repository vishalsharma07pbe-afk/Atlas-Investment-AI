import os
import tempfile
import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch

from app import autonomous_research as research


class AutonomousResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"ATLAS_RESEARCH_SNAPSHOT_DB": self.temp.name + "/research.sqlite3",
            "ATLAS_AUTONOMOUS_RESEARCH_ENABLED": "true","ATLAS_BROAD_DISCOVERY_ENABLED":"false"})
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

    def test_growth_driver_projection_does_not_retain_raw_holdings_or_private_fields(self):
        payload={key:None for key in ("category","coverage","top_performers","growth_outlook",
            "recommendation_status","blockers","notice","filters","historical_coverage")}
        payload.update(category="LARGE_CAP",top_performers=[],growth_outlook=[],
            growth_driver_review={"methodology":"MF-QUARTERLY-DRIVERS-1","status":"MATCHED_HISTORICAL_DRIVERS",
                "items":[{"identifier":"123456","name":"Example","portfolio_date":"2026-10-31","quarter":"2026-09-30",
                    "nav_date":"2026-11-26","joint_coverage_weight_percent":80,"joint_growth_weight_percent":70,
                    "review_weight_percent":10,"state":"POSITIVE_HISTORICAL_DRIVERS_ONLY","qualified":False,
                    "forecast_return_percent":None,"raw_holdings":"DO_NOT_PERSIST"}]})
        with patch.object(research,"dashboard",return_value=payload):
            snapshot=research.fund_snapshot("LARGE_CAP")
        self.assertNotIn("DO_NOT_PERSIST",str(snapshot))
        self.assertEqual(snapshot["growth_driver_review"]["items"][0]["nav_date"],"2026-11-26")
        self.assertTrue(research._published_evidence_current("LARGE_CAP",snapshot,date(2026,11,27)))
        self.assertFalse(research._published_evidence_current("LARGE_CAP",snapshot,date(2026,12,5)))

    def test_optional_analyst_model_cache_failure_preserves_current_research(self):
        import sqlite3
        from app import investment_analyst, analyst_committee
        report={"methodology":investment_analyst.VERSION,"status":"RESEARCH_AVAILABLE",
                "stocks":[{"isin":"INE002A01018","qualified":False}],"funds":[],"next_steps":["Review"]}
        def broken(r,*args):
            r["stocks"].clear()
            raise sqlite3.OperationalError("invalid cache")
        with patch.object(research,"read_snapshot",return_value={"enabled":True}), \
             patch.object(research.research_display_archive,"display",return_value=[]), \
             patch.object(investment_analyst,"analyze",return_value=report), \
             patch.object(analyst_committee,"attach",side_effect=broken):
            result=research.read_overview()["investment_analyst"]
        self.assertEqual(result["status"],"RESEARCH_AVAILABLE")
        self.assertEqual(len(result["stocks"]),1)
        self.assertEqual(result["committee"]["status"],"UNAVAILABLE")

    def test_fund_snapshot_retains_only_public_forward_scenario(self):
        payload={key:None for key in ("category","coverage","top_performers","growth_outlook",
            "recommendation_status","blockers","notice","filters","historical_coverage")}
        payload["growth_driver_review"]={"methodology":"MF-QUARTERLY-DRIVERS-1","items":[
            {"qualified":False,"quarter":"2026-09-30","experimental_forward":{
                "status":"UNCALIBRATED_PERSISTENCE_EXPERIMENT","qualified":False,
                "observed_quarter":"2026-09-30","target_quarter":"2026-12-31",
                "covered_weight_percent":80,"positive_joint_growth_weight_percent":65,
                "covered_subset_revenue_persistence_percent":10,"covered_subset_profit_persistence_percent":15,
                "private_marker":"DO_NOT_PERSIST"}}]}
        with patch.object(research,"dashboard",return_value=payload), \
             patch.object(research,"now",return_value=datetime(2026,11,28,5,tzinfo=timezone.utc)):
            snapshot=research.fund_snapshot("LARGE_CAP")
        scenario=snapshot["growth_driver_review"]["items"][0]["experimental_forward"]
        self.assertEqual(scenario["covered_subset_profit_persistence_percent"],15)
        self.assertNotIn("DO_NOT_PERSIST",str(snapshot))

    def test_fund_shortlist_snapshot_is_bounded_and_dates_rechecked(self):
        payload={key:None for key in ("category","coverage","top_performers","growth_outlook",
            "recommendation_status","blockers","notice","filters","historical_coverage")}
        payload.update(category="LARGE_CAP",top_performers=[],growth_outlook=[],
            historical_coverage={"comparison_date":"2026-11-26","items":[]},
            historical_research_shortlist={"methodology":"MF-MATCHED-PEER-1","category":"LARGE_CAP","last_date":"2026-11-26",
                "items":[{"identifier":"123456","name":"Fund","nav_date":"2026-11-26","score":75,"qualified":False,
                          "status":"HISTORICAL_RESEARCH_ONLY","private_marker":"DO_NOT_PERSIST"}]})
        with patch.object(research,"dashboard",return_value=payload):
            snapshot=research.fund_snapshot("LARGE_CAP")
        self.assertNotIn("DO_NOT_PERSIST",str(snapshot))
        self.assertEqual(len(snapshot["historical_research_shortlist"]["items"]),1)
        self.assertTrue(research._published_evidence_current("LARGE_CAP",snapshot,date(2026,11,27)))
        self.assertFalse(research._published_evidence_current("LARGE_CAP",snapshot,date(2026,12,4)))
        snapshot["historical_research_shortlist"]["items"][0]["qualified"]=True
        self.assertFalse(research._published_evidence_current("LARGE_CAP",snapshot,date(2026,11,27)))

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
             patch.object(research.automatic_company_evidence,"refresh",return_value="AVAILABLE") as company, \
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

    def test_broad_discovery_crosses_400_and_merges_exact_winners(self):
        from urllib.parse import parse_qs,urlsplit
        from datetime import date,timedelta
        total=421
        rows=[{"id":i,"exchange":"NSE","symbol":f"S{i:04d}","active":True,
               "listing_status":"ACTIVE","series":"EQ","instrument_type":"EQ",
               "recent_registry_count":total,"expected_session":"2026-11-23",
               "expected_session_count":total} for i in range(1,total+1)]
        calls=[]
        def load(path):
            args=parse_qs(urlsplit(path).query)
            self.assertEqual(args.get("cutoff"),["2026-11-24T12:00:00+00:00"])
            if "discovery-universe-page?" in path:
                after=int(args["afterId"][0]);calls.append(after)
                return [r for r in rows if r["id"]>after][:200]
            ids=list(map(int,args["ids"]))
            self.assertLessEqual(len(ids),20)
            return [{"instrument_id":i,"trade_date":(date(2026,10,31)+timedelta(days=d)).isoformat(),
              "open":100,"high":200,"low":90,"close":100 if d<23 else 100+i/10,
              "volume":100000,"adjustment_status":"ADJUSTED","revision":1} for i in ids for d in range(24)]
        with patch.dict(os.environ,{"ATLAS_BROAD_DISCOVERY_ENABLED":"true"}),patch.object(research,"now",return_value=datetime(2026,11,24,12,tzinfo=timezone.utc)),patch.object(research,"backend_json",side_effect=load):
            result=research.market_snapshot("NSE")
        self.assertEqual(calls,[0,200,400,421])
        self.assertEqual(result["universe_size"],total)
        self.assertEqual(result["eligible_count"],total)
        self.assertTrue(result["discovery_coverage"]["scan_complete"])
        self.assertEqual([r["id"] for r in result["top_gainers"]],[421,420,419,418,417])
        self.assertEqual([r["id"] for r in result["top_losers"]],[1,2,3,4,5])
        self.assertEqual([r["id"] for r in result["momentum_leaders"]],[421,420,419,418,417])
        self.assertEqual(result["sample_breadth"]["pairs"][0]["advancing"],total)

    def test_broad_annual_depth_and_legacy_bounds(self):
        from datetime import date,timedelta
        instant=datetime(2026,11,24,12,tzinfo=timezone.utc)
        instruments=[{"id":i,"exchange":"NSE","symbol":f"T{i}","active":True,
                      "listing_status":"ACTIVE","series":"EQ","instrument_type":"EQ",
                      "recent_registry_count":2,"expected_session":"2026-11-23",
                      "expected_session_count":2} for i in (1,2)]
        last=date(2026,11,23)
        def rows(depth):
            return [{"instrument_id":i,"trade_date":(last-timedelta(days=n-1-d)).isoformat(),
                     "open":100,"high":102,"low":99,"close":101,"volume":100000,
                     "adjustment_status":"RAW_UNADJUSTED"}
                    for i,n in ((1,depth),(2,250)) for d in range(n)]
        with patch.object(research,"now",return_value=instant):
            with patch.object(research,"backend_json",return_value=rows(253)):
                result=research._market_page("NSE",instruments,instant.isoformat())
                self.assertEqual(result["eligible_count"],2)
                self.assertEqual(result["discovery_coverage"]["annual_depth_count"],1)
                self.assertEqual(result["discovery_coverage"]["history_limit"],253)
                with self.assertRaisesRegex(ValueError,"LIMIT_EXCEEDED|INVALID_DISCOVERY_HISTORY"):
                    research._market_page("NSE",instruments)
            with patch.object(research,"backend_json",return_value=rows(254)):
                with self.assertRaisesRegex(ValueError,"LIMIT_EXCEEDED|INVALID_DISCOVERY_HISTORY"):
                    research._market_page("NSE",instruments,instant.isoformat())

    def test_broad_discovery_rejects_missing_duplicate_or_changed_pages(self):
        from app import discovery_scan
        instant=datetime(2026,11,24,12,tzinfo=timezone.utc)
        row={"id":1,"recent_registry_count":2,"expected_session":"2026-11-23","expected_session_count":2}
        part={"universe_size":1,"discovery_coverage":{"calendar_checked_on":"2026-11-24"}}
        for pages,code in (([[row],[]],"INCOMPLETE"),([[row],[row]],"CURSOR"),
              ([[row],[{**row,"id":2,"recent_registry_count":3}]],"CHANGED")):
            with self.subTest(code=code),patch.object(research,"backend_json",side_effect=pages):
                with self.assertRaisesRegex(ValueError,code):
                    discovery_scan.scan("NSE",research.backend_json,lambda e,p,cutoff:part,lambda:instant)

    def test_display_archive_survives_empty_refresh_without_qualifying_or_redating(self):
        from datetime import timedelta
        instant=datetime(2026,11,26,4,tzinfo=timezone.utc)
        initial={"exchange":"NSE","momentum_leaders":[{"id":1,"symbol":"TCS","exchange":"NSE",
            "as_of":"2026-11-25","momentum_20d_percent":5,"private_marker":"not stored"}]}
        with patch.dict(os.environ,{"MARKET_DATA_USAGE_RIGHTS_CONFIRMED":"true"}):
            with patch.object(research,"now",return_value=instant):
                research._save("NSE",initial)
            with patch.object(research,"now",return_value=instant+timedelta(hours=2)):
                research._save("NSE",{"exchange":"NSE","momentum_leaders":[]})
                current=research.read_market_snapshot()
                self.assertEqual(current["sections"][0]["status"],"READY")
                self.assertEqual(current["sections"][0]["result"]["momentum_leaders"],[])
                self.assertNotIn("historical_display",current)
                archive=research.research_display_archive.display(research._connect,current,research.now())
                self.assertEqual(archive[0]["generated_at"],instant.isoformat())
                self.assertFalse(archive[0]["qualification_eligible"])
                self.assertEqual(archive[0]["observations"],[{"label":"TCS","observed_date":"2026-11-25","value_percent":5}])
                self.assertNotIn("private_marker",str(archive))
                with patch.dict(os.environ,{"MARKET_DATA_USAGE_RIGHTS_CONFIRMED":"false"}):
                    self.assertEqual(research.research_display_archive.display(research._connect,current,research.now()),[])
                self.assertEqual(research.research_display_archive.display(research._connect,current,instant+timedelta(days=8)),[])

    def test_legacy_fund_snapshot_is_archived_on_failed_refresh_and_hidden_after_recovery(self):
        from datetime import timedelta
        instant=datetime(2026,11,26,4,tzinfo=timezone.utc)
        item={"scheme_code":123456,"scheme_name":"Example Fund","nav_date":"2026-11-25","cagr_3y_percent":12}
        result={"category":"LARGE_CAP","historical_coverage":{"comparison_date":"2026-11-25","items":[item]}}
        with patch.dict(os.environ,{"MARKET_DATA_USAGE_RIGHTS_CONFIRMED":"false"}),patch.object(research,"now",return_value=instant):
            research._save("LARGE_CAP",result)
        with patch.dict(os.environ,{"MARKET_DATA_USAGE_RIGHTS_CONFIRMED":"true"}),patch.object(research,"now",return_value=instant+timedelta(hours=2)):
            research._save("LARGE_CAP")
            current=research.read_snapshot(False)
            self.assertEqual(next(s for s in current["sections"] if s["section"]=="LARGE_CAP")["status"],"FAILED")
            archive=research.research_display_archive.display(research._connect,current,research.now())
            self.assertEqual(archive[0]["metric"],"3_YEAR_CAGR")
            self.assertEqual(archive[0]["generated_at"],instant.isoformat())
            self.assertNotIn("123456",str(archive))
            research._save("LARGE_CAP",result)
            self.assertEqual(research.research_display_archive.display(research._connect,research.read_snapshot(False),research.now()),[])

    def test_late_reported_action_invalidates_current_market_snapshot_for_all_consumers(self):
        from app.corporate_action_normalization import normalize_reported_actions
        from app import automatic_company_evidence as company
        from contextlib import closing
        import json
        now=datetime(2026,11,28,5,tzinfo=timezone.utc)
        isin="INE002A01018"
        result={"company_research_universe":[{"id":1,"exchange":"NSE","isin":isin,"first_date":"2026-06-01","as_of":"2026-11-27"}]}
        report={"isin":isin,"sections":{"corporate_actions":{"status":"AVAILABLE","source":{"provider":"UPSTOX",
            "endpoint":"/v2/fundamentals/"+isin+"/corporate-actions","retrieved_at":now.isoformat()},
            "data":normalize_reported_actions([{"name":"Split","expiry_date":"2026-11-25","ratio":"1:2"}])}}}
        with patch.object(research,"now",return_value=now),patch.object(company,"permitted",return_value=True):
            research._save("NSE",result)
            research._save("BSE",{"company_research_universe":[]})
            self.assertEqual(research.read_market_snapshot()["sections"][0]["status"],"READY")
            with closing(research._connect()) as db,db:
                company._table(db)
                db.execute("INSERT INTO automatic_company_evidence VALUES(?,?,?,?,?)",
                    (isin,now.isoformat(),now.isoformat(),"PARTIAL",json.dumps(report)))
            for snapshot in (research.read_market_snapshot(),research.read_snapshot(False)):
                self.assertEqual(snapshot["sections"][0]["status"],"STALE")
                self.assertEqual(snapshot["sections"][0]["error_code"],"NEW_REPORTED_ACTION_RESCAN_REQUIRED")
                self.assertEqual(snapshot["sections"][1]["status"],"READY")
            with closing(research._connect()) as db,db:
                company._archive(db,report,isin,now)
                db.execute("DELETE FROM automatic_company_evidence")
            later=now+__import__("datetime").timedelta(hours=25)
            self.assertEqual(company.cached_action_events(research._connect,[isin],later)[isin],
                [{"date":"2026-11-25","action_type":"SPLIT"}])
            research._save("NSE",{"company_research_universe":[]})
            self.assertEqual(research.read_market_snapshot()["sections"][0]["status"],"READY")

    def test_fund_targets_persist_only_compact_public_current_composition_references(self):
        payload={key:None for key in ("category","coverage","top_performers","growth_outlook",
            "recommendation_status","blockers","notice","filters","historical_coverage")}
        payload.update(category="LARGE_CAP",top_performers=[],growth_outlook=[],portfolio_evidence={"items":[
          {"status":"SECONDARY_COMPOSITION_ONLY","source":"TIGZIG_AMC_DERIVED","fund_id":"fund:123",
           "scheme_code":"123456","portfolio_date":"2026-10-31","equities":"DO_NOT_PERSIST"}]})
        now=datetime(2026,11,28,5,tzinfo=timezone.utc)
        with patch.object(research,"dashboard",return_value=payload):
            snapshot=research.fund_snapshot("LARGE_CAP")
        self.assertNotIn("DO_NOT_PERSIST",str(snapshot))
        self.assertEqual(snapshot["portfolio_research_targets"],[{"fund_id":"fund:123","scheme_code":"123456","portfolio_date":"2026-10-31"}])
        with patch.object(research,"now",return_value=now),patch.object(research.fund_portfolios,"permitted",return_value=True),patch.object(research.automatic_company_evidence,"permitted",return_value=True):
            research._save("LARGE_CAP",snapshot)
            self.assertEqual(research._fund_research_targets(now),{"fund:123":"2026-10-31"})
        with patch.object(research.fund_portfolios,"permitted",return_value=False):
            self.assertEqual(research._fund_research_targets(now),{})

    def test_fund_target_storage_failure_preserves_existing_acquisition_path(self):
        now=datetime(2026,11,28,5,tzinfo=timezone.utc)
        with patch.object(research,"_read_sections",side_effect=OSError("storage unavailable")):
            self.assertEqual(research._fund_research_targets(now),{})

    def test_scheduled_fund_snapshot_keeps_exact_bounded_decision_evidence(self):
        from app import research_synthesis as s
        payload={key:None for key in ("category","coverage","top_performers","growth_outlook","recommendation_status","blockers","notice","filters","historical_coverage")}
        row={"identifier":"123456","isin_growth":"INF123456789","name":"Example Fund","nav_date":"2026-11-27","score":90,"weekly_cagr_percent":15,"weekly_drawdown_percent":-20,"annualized_volatility_percent":15,"qualified":False,"status":"HISTORICAL_RESEARCH_ONLY"}
        payload["historical_research_shortlist"]={"methodology":"MF-MATCHED-PEER-1","category":"LARGE_CAP","status":"HISTORICAL_SHORTLIST_AVAILABLE","items":[row]}
        detail={"identifier":"123456","nav_date":"2026-11-27","category":"LARGE_CAP","plan":"DIRECT","option":"GROWTH","automatic_amfi_ter_evidence":{"status":"OPERATOR_CROSSWALK_MATCH","isin_growth":row["isin_growth"],"ter_date":"2026-11-27","ter_percent":.7,"source_url":"https://example.invalid/DO_NOT_PERSIST"},"raw_holdings":"DO_NOT_PERSIST"}
        payload["research_reports"]=[detail]
        with patch.object(research,"dashboard",return_value=payload),patch.object(research,"now",return_value=datetime(2026,11,28,5,tzinfo=timezone.utc)):
            snapshot=research.fund_snapshot("LARGE_CAP")
        self.assertNotIn("DO_NOT_PERSIST",str(snapshot))
        self.assertNotIn("research_reports",snapshot)
        saved=snapshot["fund_decision_evidence"]
        row=snapshot["historical_research_shortlist"]["items"][0]
        self.assertEqual(row["weekly_drawdown_percent"],-20)
        self.assertEqual(s.saved_fund_context(row,saved,"LARGE_CAP",date(2026,11,28),website=True,local=False,tri=False,secondary=False)["ter_percent"],.7)
        self.assertNotIn("ter_percent",s.saved_fund_context(row,saved,"LARGE_CAP",date(2026,11,28),website=False,local=False,tri=False,secondary=False))
        self.assertNotIn("ter_percent",s.saved_fund_context(row,saved,"MID_CAP",date(2026,11,28),website=True,local=False,tri=False,secondary=False))

    def test_fund_evidence_does_not_replace_section_index(self):
        # Regression for portfolio-opportunities HTTP 500: first fund
        # evidence list must not shadow the map of persisted section rows.
        research.refresh_once(lambda exchange: {"exchange":exchange},
            lambda category: {"category":category,"fund_decision_evidence":[]})
        result=research.read_snapshot(include_ai=False)
        self.assertEqual(len(result["sections"]),len(research.SECTIONS))
        self.assertEqual([r["section"] for r in result["sections"]],list(research.SECTIONS))
        self.assertTrue(all(r["status"]=="READY" for r in result["sections"]))
