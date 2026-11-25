"""Automatic bounded public strategy replay cache, independent of current picks."""
from contextlib import closing
from datetime import date,datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import json
from .market_client import backend_json
from .strategy_validation import replay, WINDOWS, attach_market_benchmark
from .horizon_research import VERSION
from .replay_evidence import (VERSION as EVIDENCE_VERSION, exact_isin, fingerprint,
    full_manifest, corporate_action_status, revision_audit, session_audit, listing_audit)
CACHE_VERSION = VERSION + ':' + EVIDENCE_VERSION + ':market-price-index-v1:signal-regime-v1:chronological-folds-v1:execution-proxy-v1:full-provenance-v1:session-continuity-v1:listing-evidence-v1'

IST=ZoneInfo("Asia/Kolkata")
def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS strategy_validation(
        exchange TEXT NOT NULL, instrument_id INTEGER NOT NULL, symbol TEXT NOT NULL,
        methodology TEXT NOT NULL, attempted_at TEXT NOT NULL,status TEXT NOT NULL,payload TEXT,
        PRIMARY KEY(exchange,instrument_id))""")

def refresh(snapshot,connect,loader=backend_json,instant=None):
    if not snapshot["enabled"]:
        return
    instant=instant or datetime.now(timezone.utc)
    today=instant.astimezone(IST).date()
    for exchange in ("NSE","BSE"):
        if not any(s["section"]==exchange and s["status"]=="READY" for s in snapshot["sections"]):
            continue
        try:
            instruments=loader(f"/api/v1/market-data/discovery-universe?exchange={exchange}")
            registry={r["id"]:r for r in instruments if type(r.get("id")) is int and r["id"]>0
                and r.get("active") is True and r.get("listing_status")=="ACTIVE"
                and r.get("series")=="EQ" and r.get("exchange")==exchange
                and r.get("instrument_type") in ("EQUITY","EQ","STOCK") and exact_isin(r.get("isin"))}
        except Exception:
            continue
        if not registry:
            continue
        stamp=instant.isoformat()
        with closing(connect()) as db,db:
            _table(db)
            db.execute("BEGIN IMMEDIATE")
            existing={r["instrument_id"]:r for r in db.execute("SELECT * FROM strategy_validation WHERE exchange=?",(exchange,))}
            due=[r for i,r in registry.items() if i not in existing or existing[i]["methodology"]!=CACHE_VERSION
                or existing[i]["attempted_at"]<=(instant-timedelta(hours=24)).isoformat()]
            if not due:
                continue
            selected=min(due,key=lambda r:(existing[r["id"]]["attempted_at"] if r["id"] in existing else "",r["id"]))
            i=selected["id"]
            previous_payload=json.loads(existing[i]["payload"] or "{}") if i in existing else {}
            prior_manifest=previous_payload.get("_history_manifest") if previous_payload.get("isin")==selected["isin"] else None
            db.execute("""INSERT INTO strategy_validation VALUES(?,?,?,?,?,'RUNNING',NULL)
                ON CONFLICT(exchange,instrument_id) DO UPDATE SET symbol=excluded.symbol,methodology=excluded.methodology,
                attempted_at=excluded.attempted_at,status='RUNNING',payload=NULL""",(exchange,i,selected["symbol"],CACHE_VERSION,stamp))
        manifest=None
        try:
            payload=loader(f"/api/v1/market-data/instruments/{i}/candles?limit=500")
            identity=payload["instrument"]
            if (identity["id"]!=i or identity["symbol"]!=selected["symbol"] or identity["exchange"]!=exchange
                    or identity.get("isin")!=selected["isin"]):
                raise ValueError("IDENTITY_MISMATCH")
            positions={}
            result=replay(payload,today,positions=positions)
            if result["status"]=="HISTORICAL_REPLAY_ONLY":
                manifest=full_manifest(payload["candles"],today)
                if manifest is None:
                    result={"status":"FULL_HISTORY_EVIDENCE_GAP","horizons":{}}
                else:
                    action=corporate_action_status(selected,manifest)
                    audit=revision_audit(manifest,prior_manifest)
                    audit["corporate_action_status"]=action
                    audit["notice"]="Full bounded replay input fingerprint, compared with the previous local capture only. No recorded crossing action does not verify adjustment completeness or point-in-time availability."
                    listing=listing_audit(selected,identity,manifest,today)
                    audit["listing_evidence"]=listing
                    if listing["status"] in ("LISTING_CONTEXT_CHANGED","LISTING_CONTEXT_CONTRADICTION"):
                        result={"status":listing["status"],"horizons":{},"listing_evidence":listing}
                    elif action!="NO_RECORDED_CROSSING_ACTION":
                        result={"status":action,"horizons":{}}
                    else:
                        try:
                            calendar=loader(f"/api/v1/market-data/strategy-calendar?exchange={exchange}")
                        except Exception:
                            calendar=None
                        continuity=session_audit(manifest,calendar,exchange,today)
                        if continuity["status"]!="STORED_SESSIONS_MATCHED":
                            result={"status":continuity["status"],"horizons":{},"calendar_continuity":continuity}
                        else:
                            try:
                                benchmark=loader("/api/v1/market-data/strategy-benchmark")
                            except Exception:
                                benchmark=None
                            attach_market_benchmark(result,payload,benchmark,today,positions=positions)
                            for horizon in result["horizons"].values():
                                horizon["history_provenance"]={**audit,"calendar_continuity":continuity}
            result["isin"]=identity["isin"]
            result["replay_evidence_hash"]=fingerprint(payload["candles"],today)
        except Exception:
            result={"status":"UNAVAILABLE","horizons":{}}
        # Keep the last successful manifest through transient failures; raw
        # per-date digests stay in this local cache, not in research responses.
        result["isin"]=selected["isin"]
        if manifest is not None or prior_manifest is not None:
            result["_history_manifest"]=manifest if manifest is not None else prior_manifest
        with closing(connect()) as db,db:
            db.execute("""UPDATE strategy_validation SET status=?,payload=? WHERE exchange=? AND instrument_id=?
                AND attempted_at=?""",(result["status"],json.dumps(result,allow_nan=False),exchange,i,stamp))
            db.execute("DELETE FROM strategy_validation WHERE attempted_at<?",((instant-timedelta(days=7)).isoformat(),))

def read(connect,instant=None,*,snapshot=None):
    instant=instant or datetime.now(timezone.utc)
    today=instant.astimezone(IST).date()
    with closing(connect()) as db:
        _table(db)
        rows=db.execute("""SELECT * FROM strategy_validation WHERE methodology=? AND attempted_at BETWEEN ? AND ?
            ORDER BY exchange,instrument_id""",(CACHE_VERSION,(instant-timedelta(hours=48)).isoformat(),instant.isoformat())).fetchall()
    if snapshot is not None and snapshot.get("enabled"):
        # Match the cached replay by registry ID, venue, symbol and observation
        # date, not by ticker alone or membership in the public top-ten sample.
        indexed={(r["exchange"],r["instrument_id"]):r for r in rows}
        for section in snapshot.get("sections",[]):
            if section.get("status")!="READY" or section.get("section") not in ("NSE","BSE"):
                continue
            for horizon in WINDOWS:
                for item in (section.get("result") or {}).get("horizons",{}).get(horizon,{}).get("candidates",[]):
                    item.pop("matched_strategy_replay",None)
                    row=indexed.get((section["section"],item.get("id")))
                    if row is None or row["symbol"]!=item.get("symbol") or item.get("exchange")!=section["section"]:
                        continue
                    payload=json.loads(row["payload"] or "{}")
                    replay_result=payload.get("horizons",{}).get(horizon,{})
                    if (exact_isin(item.get("isin")) and item["isin"]==payload.get("isin")
                            and item.get("replay_evidence_hash") is not None
                            and item["replay_evidence_hash"]==payload.get("replay_evidence_hash")
                            and item.get("adjustment_status")=="ADJUSTED"
                            and payload.get("as_of")==item.get("as_of") and replay_result.get("status")=="REPLAY_OBSERVED"
                            and replay_result.get("history_provenance",{}).get("status") in ("OVERLAP_UNCHANGED","NO_COMPARABLE_PRIOR_CAPTURE")
                            and replay_result.get("history_provenance",{}).get("corporate_action_status")=="NO_RECORDED_CROSSING_ACTION"
                            and replay_result.get("history_provenance",{}).get("calendar_continuity",{}).get("status")=="STORED_SESSIONS_MATCHED"
                            and replay_result.get("history_provenance",{}).get("listing_evidence",{}).get("status")=="RECORDED_LISTING_DATES_CONSISTENT"
                            and 1<=(today-date.fromisoformat(payload["as_of"])).days<=5):
                        item["matched_strategy_replay"]={"as_of":payload["as_of"],"attempted_at":row["attempted_at"],
                            **replay_result,"notice":"Exact ISIN and shared recent adjusted history match the cached replay. Full history was audited at replay time, not revalidated by this snapshot; later revisions and missing corporate actions remain possible. Not a forward performance estimate."}
    horizons={}
    for horizon in WINDOWS:
        items=[]
        counts={}
        calendar_withheld=[]
        listing_withheld=[]
        for row in rows:
            payload=json.loads(row["payload"] or "{}")
            result=payload.get("horizons",{}).get(horizon)
            status=result["status"] if result else row["status"]
            if result:
                try:
                    age=(today-datetime.fromisoformat(payload["as_of"]).date()).days
                    if not 1<=age<=5:
                        status="STALE"
                except (ValueError,TypeError,KeyError):
                    status="STALE"
            counts[status]=counts.get(status,0)+1
            if payload.get("listing_evidence") and len(listing_withheld)<10:
                listing_withheld.append({"exchange":row["exchange"],"symbol":row["symbol"],**payload["listing_evidence"]})
            if payload.get("calendar_continuity") and len(calendar_withheld)<10:
                calendar_withheld.append({"exchange":row["exchange"],"symbol":row["symbol"],**payload["calendar_continuity"]})
            if result and status=="REPLAY_OBSERVED":
                items.append({"exchange":row["exchange"],"symbol":row["symbol"],"as_of":payload["as_of"],**result})
        horizons[horizon]={"counts":counts,"observed_instruments":len(items),"items":items[:10],"calendar_withheld":calendar_withheld,"listing_withheld":listing_withheld}
    return {"methodology":VERSION,"evidence_version":EVIDENCE_VERSION,"sample_count":len(rows),"horizons":horizons,
        "universe_basis":"CURRENT_ACTIVE_REGISTRY_SAMPLE","historical_universe_verified":False,
        "notice":"Bounded rotating current-registry sample, not selected by current watch score. Delisted/suspended historical membership is not established; survivorship and selection bias remain. Per-instrument replay only; results are not independent or a portfolio backtest. Nifty 50 price-index comparison and signal-date trend cohorts require matching observed dates; Repeated fixed-rule test windows are descriptive; no prospective validation. No recommendation gate is lifted."}
