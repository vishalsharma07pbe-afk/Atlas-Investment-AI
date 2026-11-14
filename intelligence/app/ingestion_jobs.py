"""Fail-closed local ingestion job ledger. No provider calls or credential storage."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os
import sqlite3
import threading

DB_PATH = Path(os.getenv("ATLAS_INGESTION_DB_PATH", "/app/ingestion-data/jobs.sqlite3"))
_LOCK = threading.RLock()
MAX_ATTEMPTS = 5
ALLOWED_KINDS = frozenset({"NAV_IMPORT", "OHLCV_IMPORT", "INSTRUMENT_IMPORT"})

def _now():
    return datetime.now(timezone.utc)

def _db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH), timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS ingestion_jobs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      kind TEXT NOT NULL, source_reference TEXT NOT NULL,
      idempotency_key TEXT NOT NULL UNIQUE, status TEXT NOT NULL,
      attempts INTEGER NOT NULL DEFAULT 0, next_attempt_at TEXT,
      last_error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_ingestion_status ON ingestion_jobs(status,next_attempt_at)")
    return db

def enqueue(kind: str, source_reference: str, idempotency_key: str):
    if kind not in ALLOWED_KINDS:
        raise ValueError("UNSUPPORTED_INGESTION_KIND")
    if not 1 <= len(source_reference) <= 200 or not 1 <= len(idempotency_key) <= 120:
        raise ValueError("INVALID_REFERENCE")
    if any(x in (source_reference + idempotency_key).lower() for x in ("access_token=", "bearer ", "api_key=")):
        raise ValueError("CREDENTIAL_LIKE_REFERENCE")
    now = _now().isoformat()
    with _LOCK, _db() as db:
        db.execute("""INSERT OR IGNORE INTO ingestion_jobs
          (kind,source_reference,idempotency_key,status,created_at,updated_at)
          VALUES(?,?,?,'PENDING',?,?)""",
          (kind,source_reference,idempotency_key,now,now))
        row = db.execute("SELECT * FROM ingestion_jobs WHERE idempotency_key=?", (idempotency_key,)).fetchone()
        if row["kind"] != kind or row["source_reference"] != source_reference:
            raise ValueError("IDEMPOTENCY_KEY_CONFLICT")
        db.commit()
        return dict(row)

def claim(job_id: int):
    """Claim only due work; caller must separately verify source authorization."""
    now = _now().isoformat()
    with _LOCK, _db() as db:
        row = db.execute("SELECT * FROM ingestion_jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise ValueError("JOB_NOT_FOUND")
        if row["status"] not in ("PENDING", "RETRY") or (row["next_attempt_at"] and row["next_attempt_at"] > now):
            raise ValueError("JOB_NOT_DUE")
        db.execute("""UPDATE ingestion_jobs SET status='RUNNING',attempts=attempts+1,
            next_attempt_at=NULL,updated_at=? WHERE id=?""", (now,job_id))
        db.commit()
        return dict(db.execute("SELECT * FROM ingestion_jobs WHERE id=?", (job_id,)).fetchone())

def finish(job_id: int, succeeded: bool, error_code: str = ""):
    if error_code and (len(error_code) > 80 or not all(c.isupper() or c.isdigit() or c == "_" for c in error_code)):
        raise ValueError("ERROR_CODE_MUST_BE_NON_SENSITIVE")
    now = _now()
    with _LOCK, _db() as db:
        row = db.execute("SELECT * FROM ingestion_jobs WHERE id=?", (job_id,)).fetchone()
        if row is None or row["status"] != "RUNNING":
            raise ValueError("JOB_NOT_RUNNING")
        if succeeded:
            status, next_at, code = "SUCCEEDED", None, None
        elif row["attempts"] >= MAX_ATTEMPTS:
            status, next_at, code = "FAILED", None, error_code or "INGESTION_FAILED"
        else:
            status, next_at, code = "RETRY", (now + timedelta(seconds=min(3600, 30 * 2 ** (row["attempts"] - 1)))).isoformat(), error_code or "INGESTION_FAILED"
        db.execute("""UPDATE ingestion_jobs SET status=?,next_attempt_at=?,last_error=?,updated_at=?
            WHERE id=?""", (status,next_at,code,now.isoformat(),job_id))
        db.commit()
        return dict(db.execute("SELECT * FROM ingestion_jobs WHERE id=?", (job_id,)).fetchone())

def status(limit: int = 30):
    if not 1 <= limit <= 100:
        raise ValueError("INVALID_LIMIT")
    with _LOCK, _db() as db:
        rows = db.execute("SELECT * FROM ingestion_jobs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return {"jobs": [dict(row) for row in rows], "automatic_execution_enabled": False,
                "notice": "Ledger only. No provider requests or unattended imports are initiated."}
