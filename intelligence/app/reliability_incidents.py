"""Fail-closed local data-reliability incident snapshots; never enables a provider."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import sqlite3
import threading

DB_PATH = Path(os.getenv("ATLAS_RELIABILITY_DB_PATH", "/app/reliability-data/incidents.sqlite3"))
_LOCK = threading.RLock()
ALLOWED = {"MISSING", "STALE", "FUTURE_TIMESTAMP", "STORAGE_ERROR", "UNVERIFIED_SOURCE", "BLOCKED"}
MAX_ISSUES = 100

def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH), timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS reliability_incidents(
        fingerprint TEXT PRIMARY KEY, dataset TEXT NOT NULL, code TEXT NOT NULL,
        first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, occurrences INTEGER NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('OPEN','RESOLVED')))""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_reliability_last_seen ON reliability_incidents(last_seen)")
    return db

def _normalize(issues):
    if not isinstance(issues, list) or len(issues) > MAX_ISSUES:
        raise ValueError("INVALID_ISSUE_COUNT")
    normalized = set()
    for item in issues:
        if not isinstance(item, dict):
            raise ValueError("INVALID_ISSUE")
        dataset, code = item.get("dataset"), item.get("code")
        if not isinstance(dataset, str) or not (1 <= len(dataset) <= 64) or not all(c.isalnum() or c in "_-" for c in dataset) or not dataset.isascii():
            raise ValueError("INVALID_DATASET")
        if code not in ALLOWED:
            raise ValueError("INVALID_ISSUE_CODE")
        normalized.add((dataset, code))
    return sorted(normalized)

def record_snapshot(issues):
    """Reconcile complete current issue set; absence resolves previously open issues."""
    normalized = _normalize(issues)
    now = datetime.now(timezone.utc).isoformat()
    with _LOCK, _connect() as db:
        current = set()
        for dataset, code in normalized:
            fingerprint = hashlib.sha256((dataset + ":" + code).encode()).hexdigest()
            current.add(fingerprint)
            db.execute("""INSERT INTO reliability_incidents VALUES(?,?,?,?,?,1,'OPEN')
                ON CONFLICT(fingerprint) DO UPDATE SET
                  last_seen=excluded.last_seen,
                  occurrences=reliability_incidents.occurrences+1,
                  state='OPEN'""", (fingerprint, dataset, code, now, now))
        if current:
            placeholders = ",".join("?" for _ in current)
            db.execute("UPDATE reliability_incidents SET state='RESOLVED' WHERE state='OPEN' AND fingerprint NOT IN (" + placeholders + ")", tuple(sorted(current)))
        else:
            db.execute("UPDATE reliability_incidents SET state='RESOLVED' WHERE state='OPEN'")
        db.commit()
    return {"recorded_at": now, "observed_issues": len(normalized), "live_feed_connected": False}

def history(limit=50):
    if not isinstance(limit, int) or limit < 1 or limit > 100:
        raise ValueError("INVALID_LIMIT")
    with _LOCK, _connect() as db:
        rows = db.execute("SELECT dataset,code,first_seen,last_seen,occurrences,state FROM reliability_incidents ORDER BY last_seen DESC LIMIT ?", (limit,)).fetchall()
        open_count = db.execute("SELECT COUNT(*) FROM reliability_incidents WHERE state='OPEN'").fetchone()[0]
    return {"incidents": [dict(row) for row in rows], "open_count": open_count,
            "mode": "LOCAL_READINESS_OBSERVATIONS", "live_feed_connected": False,
            "automatic_collection_enabled": False}
