import sqlite3
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from app.automatic_strategy_validation import refresh,read,CACHE_VERSION
from app.horizon_research import VERSION
from unittest.mock import patch

class AutomaticValidationTests(unittest.TestCase):
    def test_rotates_registry_not_current_picks_and_avoids_repeat_within_cooldown(self):
        with tempfile.TemporaryDirectory() as directory:
            def connect():
                db=sqlite3.connect(directory+"/validation.sqlite")
                db.row_factory=sqlite3.Row
                return db
            now=datetime(2026,11,24,10,tzinfo=timezone.utc)
            snapshot={"enabled":True,"sections":[{"section":"NSE","status":"READY","result":{"horizons":{}}}]}
            calls=[]
            registry=[{"id":i,"symbol":f"TEST{i}","active":True,"listing_status":"ACTIVE","series":"EQ","exchange":"NSE","instrument_type":"EQUITY","isin":f"INE000A010{i:02d}"} for i in (1,2)]
            def loader(path):
                calls.append(path)
                if path.startswith("/api/v1/market-data/discovery-universe?"):
                    return registry
                i=int(path.split("/")[5])
                return {"instrument":{"id":i,"symbol":f"TEST{i}","exchange":"NSE","isin":f"INE000A010{i:02d}"},"candles":[]}
            with patch("app.automatic_strategy_validation.replay",return_value={"status":"INSUFFICIENT_HISTORY","horizons":{}}):
                for _ in range(3):
                    refresh(snapshot,connect,loader,now)
            self.assertEqual(sum("candles?" in x for x in calls),2)
            result=read(connect,now)
            self.assertEqual(result["sample_count"],2)
            self.assertEqual(result["horizons"]["SWING"]["counts"],{"INSUFFICIENT_HISTORY":2})
            self.assertEqual(read(connect,now+timedelta(hours=49))["sample_count"],0)
            self.assertEqual(result["methodology"],VERSION)

    def test_replay_attaches_only_exact_current_stock_and_observation(self):
        import json
        from app.automatic_strategy_validation import _table
        with tempfile.TemporaryDirectory() as directory:
            def connect():
                db=sqlite3.connect(directory+"/validation.sqlite")
                db.row_factory=sqlite3.Row
                return db
            instant=datetime(2026,11,24,10,tzinfo=timezone.utc)
            result={"as_of":"2026-11-23","isin":"INE002A01018","replay_evidence_hash":"a"*64,"horizons":{"SWING":{"status":"REPLAY_OBSERVED",
                "trades":3,"small_sample":True,"cost_scenarios":[],"history_provenance":{"status":"NO_COMPARABLE_PRIOR_CAPTURE","corporate_action_status":"NO_RECORDED_CROSSING_ACTION","calendar_continuity":{"status":"STORED_SESSIONS_MATCHED"},"listing_evidence":{"status":"RECORDED_LISTING_DATES_CONSISTENT"}}}}}
            with connect() as db:
                _table(db)
                db.execute("INSERT INTO strategy_validation VALUES(?,?,?,?,?,?,?)",
                    ("NSE",1,"TEST",CACHE_VERSION,instant.isoformat(),"HISTORICAL_REPLAY_ONLY",json.dumps(result)))
            items=[{"id":1,"symbol":"TEST","exchange":"NSE","as_of":"2026-11-23"},
                   {"id":2,"symbol":"TEST","exchange":"NSE","as_of":"2026-11-23"},
                   {"id":1,"symbol":"OTHER","exchange":"NSE","as_of":"2026-11-23"},
                   {"id":1,"symbol":"TEST","exchange":"NSE","as_of":"2026-11-22"}]
            for item in items:
                item.update({"isin":"INE002A01018","replay_evidence_hash":"a"*64,"adjustment_status":"ADJUSTED"})
            items.extend([{**items[0],"isin":"INE002A01019"},
                          {**items[0],"replay_evidence_hash":"b"*64,"matched_strategy_replay":{"trades":99}},
                          {**items[0],"replay_evidence_hash":None},
                          {**items[0],"adjustment_status":"RAW_UNADJUSTED"}])
            snapshot={"enabled":True,"sections":[{"section":"NSE","status":"READY",
                "result":{"horizons":{"SWING":{"candidates":items}}}}]}
            read(connect,instant,snapshot=snapshot)
            self.assertEqual(items[0]["matched_strategy_replay"]["trades"],3)
            self.assertTrue(all("matched_strategy_replay" not in i for i in items[1:]))
            result["horizons"]["SWING"]["history_provenance"]["listing_evidence"]["status"]="LISTING_EVIDENCE_UNAVAILABLE"
            with connect() as db:
                db.execute("UPDATE strategy_validation SET payload=?",(json.dumps(result),))
            read(connect,instant,snapshot=snapshot)
            self.assertNotIn("matched_strategy_replay",items[0])

    def test_regime_evidence_is_refreshed_and_cached_with_existing_replay(self):
        from datetime import date
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            def connect():
                db=sqlite3.connect(directory+"/validation.sqlite")
                db.row_factory=sqlite3.Row
                return db
            now=datetime(2026,11,24,10,tzinfo=timezone.utc)
            snapshot={"enabled":True,"sections":[{"section":"NSE","status":"READY","result":{"horizons":{}}}]}
            identity={"id":1,"symbol":"TEST","exchange":"NSE","isin":"INE002A01018",
                      "active":True,"listing_status":"ACTIVE","series":"EQ","instrument_type":"EQUITY",
                      "latest_action_date":None,"corporate_action_context":"[]",
                      "listed_on":"2020-01-01","delisted_on":None,"registry_source":"TEST","registry_revision":"r1"}
            today=date(2026,11,24)
            candles=[{"trade_date":(today-timedelta(days=500-i)).isoformat(),"open":100+i*.1,
                      "high":101+i*.1,"low":99+i*.1,"close":100.2+i*.1,"volume":200000,
                      "adjustment_status":"ADJUSTED","quality_status":"PROVIDER_VALIDATED","source_code":"TEST","revision":1}
                      for i in range(500)]
            benchmark={"benchmark_key":"NSE_INDEX|Nifty 50","kind":"PRICE_INDEX",
                       "candles":[{"trade_date":row["trade_date"],"open":100,"close":100+i*.2,
                                   "revision":1,"source_code":"UPSTOX"} for i,row in enumerate(candles[-300:])]}
            calls=[]
            calendar_today=[today]
            calendar_override={}
            def loader(path):
                calls.append(path)
                if "discovery-universe" in path:return [identity]
                if "strategy-calendar" in path:
                    through=calendar_today[0]-timedelta(days=1)
                    days=[{"trade_date":row["trade_date"],"state":calendar_override.get(row["trade_date"],"REGULAR")} for row in candles]
                    for i in range((calendar_today[0]-today).days):
                        days.append({"trade_date":(today+timedelta(days=i)).isoformat(),"state":"CLOSED"})
                    return {"exchange":"NSE","through":through.isoformat(),"days":days}
                if path.endswith("strategy-benchmark"):return benchmark
                return {"instrument":identity,"candles":candles}
            with patch("app.strategy_validation.evaluate",return_value={h:("TECHNICAL_WATCH",{}) for h in ("SWING","SHORT_TERM","LONG_TERM")}):
                refresh(snapshot,connect,loader,now)
                refresh(snapshot,connect,loader,now)
            result=read(connect,now)["horizons"]["SWING"]["items"][0]
            self.assertEqual(result["market_regime_research"]["classified_trades"],19)
            self.assertEqual(result["chronological_validation"]["observed_folds"],3)
            self.assertEqual(result["execution_research"]["positions"],19)
            self.assertEqual(result["execution_research"]["notional_scenarios"][0]["within_proxy_limit"],19)
            self.assertEqual(result["chronological_validation"]["folds"][0]["market_benchmark_status"],"MATCHED_PRICE_INDEX")
            self.assertEqual(sum(path.endswith("strategy-benchmark") for path in calls),1)
            self.assertEqual(result["history_provenance"]["history_observations"],500)
            self.assertEqual(result["history_provenance"]["status"],"NO_COMPARABLE_PRIOR_CAPTURE")
            self.assertEqual(result["history_provenance"]["listing_evidence"]["status"],"RECORDED_LISTING_DATES_CONSISTENT")
            self.assertNotIn("_history_manifest",result)
            # Same-date older revision is detected on the next ordinary pass.
            candles[0]["revision"]=2
            later=now+timedelta(hours=25)
            calendar_today[0]=today+timedelta(days=1)
            with patch("app.strategy_validation.evaluate",return_value={h:("TECHNICAL_WATCH",{}) for h in ("SWING","SHORT_TERM","LONG_TERM")}):
                refresh(snapshot,connect,loader,later)
                revised=read(connect,later)["horizons"]["SWING"]["items"][0]
                self.assertEqual(revised["history_provenance"]["status"],"REVISIONS_DETECTED")
                self.assertEqual(revised["history_provenance"]["changed_observations"],1)
                self.assertEqual(revised["history_provenance"]["calendar_continuity"]["status"],"STORED_SESSIONS_MATCHED")
                calendar_override[candles[100]["trade_date"]]="CLOSED"
                blocked=later+timedelta(hours=25)
                calendar_today[0]=today+timedelta(days=2)
                refresh(snapshot,connect,loader,blocked)
                report=read(connect,blocked)["horizons"]["SWING"]
                self.assertEqual(report["counts"],{"HISTORICAL_SESSION_MISMATCH":1})
                self.assertEqual(report["calendar_withheld"][0]["unexpected_observations"],1)
                self.assertEqual(report["items"],[])
                # A newly recorded crossing event withholds even provider-labeled adjusted replay.
                import json
                identity["latest_action_date"]=candles[100]["trade_date"]
                identity["corporate_action_context"]=json.dumps([{"ex_date":identity["latest_action_date"],"action_type":"SPLIT"}])
                final=blocked+timedelta(hours=25)
                calendar_today[0]=today+timedelta(days=3)
                refresh(snapshot,connect,loader,final)
                report=read(connect,final)["horizons"]["SWING"]
                self.assertEqual(report["counts"],{"RECORDED_ACTION_RECONCILIATION_REQUIRED":1})
                self.assertEqual(report["items"],[])
                identity["listed_on"]=candles[100]["trade_date"]
                refresh(snapshot,connect,loader,final+timedelta(hours=25))
                report=read(connect,final+timedelta(hours=25))["horizons"]["SWING"]
                self.assertEqual(report["counts"],{"LISTING_CONTEXT_CONTRADICTION":1})
                self.assertEqual(report["listing_withheld"][0]["listed_on"],identity["listed_on"])

