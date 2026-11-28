"""Restart-safe cooldown and bounded half-open probes for public provider HTTP.
No identifiers, credentials, request URLs or provider response bodies persist.
This ledger is shared by the existing Python equity, index and P1 HTTP adapter.
"""
from contextlib import closing
from pathlib import Path
import os
import sqlite3
import time
from uuid import uuid4

PROVIDERS=("UPSTOX","POLYGON","DHAN")
GLOBAL_PROVIDERS=("FRED","EIA","US_TREASURY","TWELVE_DATA","ECB","FED","BLS")
LEASE=30
CODES={"PROVIDER_ACCESS_REJECTED":900,"PROVIDER_RATE_LIMITED":60,
       "PROVIDER_REQUEST_FAILED":60,"PROVIDER_HTTP_FAILURE":60}


def _path():
    return Path(os.getenv("ATLAS_QUOTE_RECOVERY_DB",str(Path(os.getenv(
        "ATLAS_RESEARCH_SNAPSHOT_DB","/app/ingestion-data/research_snapshots.sqlite3")).with_name("quote_recovery.sqlite3"))))


def _connect():
    path=_path()
    path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path,timeout=2)
    db.row_factory=sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS quote_recovery(
      provider TEXT PRIMARY KEY, failures INTEGER NOT NULL DEFAULT 0,
      blocked_until REAL NOT NULL DEFAULT 0, claim_id TEXT, lease_until REAL,
      last_error TEXT, last_success REAL)""")
    return db


def claim(provider,now=None):
    if provider not in PROVIDERS+GLOBAL_PROVIDERS:
        raise ValueError("INVALID_PROVIDER")
    now=time.time() if now is None else now
    with closing(_connect()) as db,db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("INSERT OR IGNORE INTO quote_recovery(provider) VALUES(?)",(provider,))
        row=db.execute("SELECT * FROM quote_recovery WHERE provider=?",(provider,)).fetchone()
        if row["blocked_until"]>now or (row["claim_id"] and row["lease_until"]>now):
            return None
        token=uuid4().hex
        db.execute("UPDATE quote_recovery SET claim_id=?,lease_until=? WHERE provider=?",(token,now+(90 if provider in GLOBAL_PROVIDERS else LEASE),provider))
        return token


def finish(provider,token,reason=None,retry_after=None,now=None):
    now=time.time() if now is None else now
    with closing(_connect()) as db,db:
        db.execute("BEGIN IMMEDIATE")
        row=db.execute("SELECT * FROM quote_recovery WHERE provider=? AND claim_id=?",(provider,token)).fetchone()
        if not row:
            return False
        failures=row["failures"]+1 if reason in CODES else 0
        delay=1 if provider=="DHAN" else 0
        if reason in CODES:
            delay=min(3600,CODES[reason]*2**min(failures-1,5))
            if provider in GLOBAL_PROVIDERS:
                # Global publishers share a conservative minimum cooldown.
                delay=max(delay,900 if reason=="PROVIDER_ACCESS_REJECTED" else 300)
                if type(retry_after) is int:
                    delay=max(delay,retry_after)
            elif type(retry_after) is int:
                # The exponential backoff cap is ours, not the publisher's.
                # A valid longer provider instruction must remain authoritative.
                delay=max(delay,retry_after)
        db.execute("""UPDATE quote_recovery SET failures=?,blocked_until=?,claim_id=NULL,lease_until=NULL,
            last_error=?,last_success=CASE WHEN ? IS NULL THEN ? ELSE last_success END
            WHERE provider=? AND claim_id=?""",
            (failures,now+delay,reason if reason in CODES else None,reason,now,provider,token))
        return True


def status(now=None,*,global_sources=False):
    now=time.time() if now is None else now
    try:
        path=_path()
        rows={}
        if path.is_file():
            with closing(sqlite3.connect(path.resolve().as_uri()+"?mode=ro",uri=True,timeout=2)) as db:
                db.row_factory=sqlite3.Row
                rows={r["provider"]:r for r in db.execute("SELECT * FROM quote_recovery")}
        results=[]
        for provider in GLOBAL_PROVIDERS if global_sources else PROVIDERS:
            r=rows.get(provider)
            state="CLOSED" if r else "NOT_OBSERVED"
            wait=0
            if r and r["blocked_until"]>now:
                state="OPEN";wait=max(1,int(r["blocked_until"]-now))
            elif r and r["claim_id"] and r["lease_until"]>now:
                state="PROBE_IN_PROGRESS";wait=max(1,int(r["lease_until"]-now))
            elif r and (r["failures"] or r["claim_id"]):
                state="RECOVERY_PROBE_DUE"
            results.append({"provider":provider,"state":state,"retry_after_seconds":wait,
                            "failures":r["failures"] if r else 0,"last_error":r["last_error"] if r else None})
        return {"status":"PERSISTED_GLOBAL_RECOVERY" if global_sources else "PERSISTED_QUOTE_RECOVERY","providers":results}
    except (OSError,sqlite3.Error):
        return {"status":"RECOVERY_STORAGE_UNAVAILABLE","providers":[]}

def record_fallback(now=None):
    """Record only aggregate validated same-market route observations.

    No instrument, quote, account, token, or configuration fingerprint stored.
    An observation is not a standing entitlement or streaming certification.
    """
    now=time.time() if now is None else now
    try:
        with closing(_connect()) as db,db:
            db.execute("""CREATE TABLE IF NOT EXISTS same_market_fallback_observations(
              route TEXT PRIMARY KEY, last_observed REAL NOT NULL, observation_count INTEGER NOT NULL)""")
            db.execute("""INSERT INTO same_market_fallback_observations VALUES('UPSTOX_TO_DHAN',?,1)
              ON CONFLICT(route) DO UPDATE SET last_observed=max(last_observed,excluded.last_observed),
                observation_count=observation_count+1""",(now,))
        return True
    except (OSError,sqlite3.Error):
        return False


def fallback_status(now=None):
    now=time.time() if now is None else now
    result={"status":"NOT_OBSERVED","route":"UPSTOX_TO_DHAN","last_observed_at":None,"observation_count":0,
            "notice":"Aggregate past validated HTTP fallback observations only. Not proof of current configuration, feed availability or streaming."}
    try:
        path=_path()
        if not path.is_file():return result
        with closing(sqlite3.connect(path.resolve().as_uri()+"?mode=ro",uri=True,timeout=2)) as db:
            db.row_factory=sqlite3.Row
            if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='same_market_fallback_observations'").fetchone():return result
            row=db.execute("SELECT * FROM same_market_fallback_observations WHERE route='UPSTOX_TO_DHAN'").fetchone()
        if row and 0<=row["last_observed"]<=now and type(row["observation_count"]) is int and row["observation_count"]>0:
            from datetime import datetime,timezone
            result.update(status="PAST_VALIDATED_HTTP_FALLBACK",last_observed_at=datetime.fromtimestamp(row["last_observed"],timezone.utc).isoformat(),
                          observation_count=row["observation_count"])
        return result
    except (OSError,sqlite3.Error,ValueError,TypeError,OverflowError):
        return {**result,"status":"RECOVERY_STORAGE_UNAVAILABLE"}
