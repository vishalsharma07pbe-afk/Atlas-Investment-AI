"""Automatic bounded public strategy replay cache, independent of current picks."""
from contextlib import closing
from datetime import date,datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import json
from .market_client import backend_json
from .strategy_validation import replay, WINDOWS, attach_market_benchmark
from .horizon_research import VERSION
from .automatic_company_evidence import cached_action_reports, cached_action_events
from .corporate_action_normalization import reported_crossings, archived_crossings
from .replay_evidence import (VERSION as EVIDENCE_VERSION, exact_isin, fingerprint,
    full_manifest, corporate_action_status, revision_audit, session_audit, listing_audit)
CACHE_VERSION = VERSION + ':' + EVIDENCE_VERSION + ':market-price-index-v1:signal-regime-v1:chronological-folds-v1:execution-proxy-v1:full-provenance-v1:session-continuity-v1:listing-evidence-v1:scoped-action-v1:provider-action-and-rotation-v1'

IST=ZoneInfo("Asia/Kolkata")
def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS strategy_validation(
        exchange TEXT NOT NULL, instrument_id INTEGER NOT NULL, symbol TEXT NOT NULL,
        methodology TEXT NOT NULL, attempted_at TEXT NOT NULL,status TEXT NOT NULL,payload TEXT,
        PRIMARY KEY(exchange,instrument_id))""")
    # Persist the actual selection order independently of attempt timestamps.
    db.execute("""CREATE TABLE IF NOT EXISTS strategy_replay_rotation(
        exchange TEXT PRIMARY KEY, selection_basis TEXT NOT NULL)""")

def _ready_observations(snapshot,exchange,registry,today):
    """Exact eligible public identities, independent of watch scores."""
    for section in snapshot.get("sections",[]):
        if section.get("section")!=exchange or section.get("status")!="READY":
            continue
        result=section.get("result") or {}
        rows=result.get("replay_research_universe")
        count=result.get("eligible_count")
        if not isinstance(rows,list) or type(count) is not int or not 0<=len(rows)<=count<=20000:
            return {}
        ids={}
        seen=set()
        for row in rows:
            if not isinstance(row,dict) or type(row.get("id")) is not int or row["id"] in seen:
                return {}
            i=row["id"]
            seen.add(i)
            identity=registry.get(i)
            if not identity or row.get("exchange")!=exchange or row.get("isin")!=identity["isin"]:
                continue
            try:
                age=(today-date.fromisoformat(row["as_of"])).days
                if 1<=age<=4:
                    ids[i]=row["as_of"]
            except (ValueError,KeyError,TypeError):
                continue
        return ids
    return {}


def _ready_ids(snapshot,exchange,registry,today):
    return set(_ready_observations(snapshot,exchange,registry,today))


def _payload(row):
    try:
        value=json.loads(row["payload"] or "{}")
        return value if isinstance(value,dict) else {}
    except (ValueError,TypeError,KeyError):
        return {}


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
            ready=_ready_observations(snapshot,exchange,registry,today)
            def due_now(i):
                previous=existing.get(i)
                if previous is None or previous["methodology"]!=CACHE_VERSION or previous["attempted_at"]<=(instant-timedelta(hours=24)).isoformat():
                    return True
                # A newly observed completed adjusted session invalidates a
                # yesterday replay match; permit one earlier local re-audit.
                # Only advance the target after an attempted refresh, even on
                # failure, and never retry on a same-session hash fluctuation.
                if i not in ready or previous["attempted_at"]>(instant-timedelta(minutes=30)).isoformat():
                    return False
                payload=_payload(previous)
                attempted=payload.get("selection_observed_date") or payload.get("as_of")
                try:
                    return (payload.get("isin")==registry[i]["isin"] and
                            date.fromisoformat(attempted)<date.fromisoformat(ready[i]))
                except (ValueError,TypeError):return False
            due=[r for i,r in registry.items() if due_now(i)]
            if not due:
                continue
            eligible=[r for r in due if r["id"] in ready]
            general=[r for r in due if r["id"] not in ready]
            rotation=db.execute("SELECT selection_basis FROM strategy_replay_rotation WHERE exchange=?",(exchange,)).fetchone()
            last_basis=rotation["selection_basis"] if rotation else None
            # Alternate when both queues are due; never eliminate registry rotation.
            prefer_ready=bool(eligible) and (not general or last_basis!="VALIDATED_RECENT_HISTORY_HINT")
            pool=eligible if prefer_ready else general
            basis="VALIDATED_RECENT_HISTORY_HINT" if prefer_ready else "GENERAL_REGISTRY_ROTATION"
            selected=min(pool,key=lambda r:(existing[r["id"]]["attempted_at"] if r["id"] in existing else "",r["id"]))
            i=selected["id"]
            previous_payload=_payload(existing[i]) if i in existing else {}
            prior_manifest=previous_payload.get("_history_manifest") if previous_payload.get("isin")==selected["isin"] else None
            db.execute("""INSERT INTO strategy_validation VALUES(?,?,?,?,?,'RUNNING',NULL)
                ON CONFLICT(exchange,instrument_id) DO UPDATE SET symbol=excluded.symbol,methodology=excluded.methodology,
                attempted_at=excluded.attempted_at,status='RUNNING',payload=NULL""",(exchange,i,selected["symbol"],CACHE_VERSION,stamp))
            db.execute("""INSERT INTO strategy_replay_rotation(exchange,selection_basis) VALUES(?,?)
                ON CONFLICT(exchange) DO UPDATE SET selection_basis=excluded.selection_basis""",(exchange,basis))
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
                    discovered_action=corporate_action_status(selected,manifest,today=today)
                    action=corporate_action_status(identity,manifest,require_scope=True,today=today)
                    if discovered_action=="RECORDED_ACTION_RECONCILIATION_REQUIRED":
                        action=discovered_action
                    elif discovered_action!="NO_RECORDED_CROSSING_ACTION" and action=="NO_RECORDED_CROSSING_ACTION":
                        action="ACTION_CONTEXT_UNAVAILABLE"
                    # Same exact-ISIN authorized cache as discovery, no provider call.
                    cached=cached_action_reports(connect,[selected["isin"]],instant)
                    crossings=reported_crossings(cached.get(selected["isin"]),selected["isin"],
                        date.fromisoformat(manifest["first_date"]),date.fromisoformat(manifest["last_date"]),instant)
                    events=cached_action_events(connect,[selected["isin"]],instant)
                    crossings=archived_crossings([*crossings,*events.get(selected["isin"],[])],
                        date.fromisoformat(manifest["first_date"]),date.fromisoformat(manifest["last_date"]))
                    if crossings and action=="NO_RECORDED_CROSSING_ACTION":
                        action="REPORTED_ACTION_RECONCILIATION_REQUIRED"
                    audit=revision_audit(manifest,prior_manifest)
                    audit["corporate_action_status"]=action
                    audit["notice"]="Full bounded replay input fingerprint, compared with the previous local capture only. No recorded crossing action does not verify adjustment completeness or point-in-time availability."
                    listing=listing_audit(selected,identity,manifest,today)
                    audit["listing_evidence"]=listing
                    if listing["status"] in ("LISTING_CONTEXT_CHANGED","LISTING_CONTEXT_CONTRADICTION"):
                        result={"status":listing["status"],"horizons":{},"listing_evidence":listing}
                    elif action!="NO_RECORDED_CROSSING_ACTION":
                        result={"status":action,"horizons":{}}
                        if crossings:
                            result["reported_crossing_actions"]=crossings
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
                            if audit["status"] in ("OVERLAP_UNCHANGED","NO_COMPARABLE_PRIOR_CAPTURE") and listing["status"]=="RECORDED_LISTING_DATES_CONSISTENT":
                                from . import bracket_research
                                bracket=bracket_research.replay(payload,today,positions)
                                for h,report in bracket.items():
                                    if h in result["horizons"]:result["horizons"][h]["bracket_replay"]=report
                            if audit["status"] in ("OVERLAP_UNCHANGED","NO_COMPARABLE_PRIOR_CAPTURE") and listing["status"]=="RECORDED_LISTING_DATES_CONSISTENT":
                                from . import fip_research
                                fip=fip_research.replay(payload["candles"],today)
                                if fip is not None:result["fip_replay"]=fip
                            for horizon in result["horizons"].values():
                                horizon["history_provenance"]={**audit,"calendar_continuity":continuity}
            result["isin"]=identity["isin"]
            result["replay_evidence_hash"]=fingerprint(payload["candles"],today)
        except Exception:
            result={"status":"UNAVAILABLE","horizons":{}}
        # Keep the last successful manifest through transient failures; raw
        # per-date digests stay in this local cache, not in research responses.
        result["isin"]=selected["isin"]
        result["selection_basis"]=basis
        if i in ready:result["selection_observed_date"]=ready[i]
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
    fip_items=[]
    for row in rows:
        payload=_payload(row);fip=payload.get("fip_replay")
        if isinstance(fip,dict) and fip.get("status")=="DESCRIPTIVE_FIXED_RULE_REPLAY":
            try:
                if 1<=(today-date.fromisoformat(fip["as_of"])).days<=5:
                    fip_items.append({"exchange":row["exchange"],"id":row["instrument_id"],"symbol":row["symbol"],"isin":payload.get("isin"),
                        "replay_evidence_hash":payload.get("replay_evidence_hash"),**fip})
            except (ValueError,TypeError,KeyError):pass
    if snapshot is not None:
        snapshot["fip_replay_sample"]={"sample_count":len(fip_items),"items":fip_items}
    selection_counts={}
    for row in rows:
        basis=_payload(row).get("selection_basis","UNKNOWN")
        if basis not in ("VALIDATED_RECENT_HISTORY_HINT","GENERAL_REGISTRY_ROTATION"):
            basis="UNKNOWN"
        selection_counts[basis]=selection_counts.get(basis,0)+1
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
        "universe_basis":"CURRENT_ACTIVE_REGISTRY_SAMPLE","historical_universe_verified":False,"selection_counts":selection_counts,
        "notice":"Bounded rotating current-registry sample alternating recent validated adjusted-history hints with general registry entries, not selected by current watch score. History availability selection bias remains. Delisted/suspended historical membership is not established; survivorship and selection bias remain. Per-instrument replay only; results are not independent or a portfolio backtest. Nifty 50 price-index comparison and signal-date trend cohorts require matching observed dates; Repeated fixed-rule test windows are descriptive; no prospective validation. No recommendation gate is lifted."}
