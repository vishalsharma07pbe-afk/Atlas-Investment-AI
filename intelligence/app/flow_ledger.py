"""Local institutional-flow evidence ledger; never a live or independently verified feed."""
from datetime import datetime, date, timezone
from pathlib import Path
from decimal import Decimal
import hashlib
import os
import sqlite3
import threading

from .institutional_flows import FlowRequest, analyze_flows

DB_PATH = Path(os.getenv("ATLAS_FLOW_DB_PATH", "/app/flow-data/flows.sqlite3"))
_LOCK = threading.RLock()

def _db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH), timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS flow_evidence (
      trade_date TEXT NOT NULL, market TEXT NOT NULL, participant TEXT NOT NULL,
      buy_crore_inr TEXT NOT NULL, sell_crore_inr TEXT NOT NULL,
      source_name TEXT NOT NULL, source_url TEXT,
      verification TEXT NOT NULL, imported_at TEXT NOT NULL,
      fingerprint TEXT NOT NULL,
      PRIMARY KEY(trade_date, market, participant))""")
    return db

def import_evidence(request: FlowRequest):
    analysis = analyze_flows(request.records)
    now = datetime.now(timezone.utc).isoformat()
    with _LOCK, _db() as db:
        # Reject conflicting evidence rather than silently overwriting source-attributed records.
        for row in analysis["records"]:
            previous = db.execute("""SELECT fingerprint FROM flow_evidence
                WHERE trade_date=? AND market=? AND participant=?""",
                (row["trade_date"],row["market"],row["participant"])).fetchone()
            fingerprint = _fingerprint(row)
            if previous and previous["fingerprint"] != fingerprint:
                raise ValueError("CONFLICTING_FLOW_EVIDENCE")
        inserted = 0
        for row in analysis["records"]:
            fingerprint = _fingerprint(row)
            cursor = db.execute("""INSERT OR IGNORE INTO flow_evidence
                (trade_date,market,participant,buy_crore_inr,sell_crore_inr,
                 source_name,source_url,verification,imported_at,fingerprint)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (row["trade_date"],row["market"],row["participant"],
                 row["buy_crore_inr"],row["sell_crore_inr"],
                 row["source_name"],row["source_url"],row["verification"],now,fingerprint))
            inserted += cursor.rowcount
        db.commit()
    return {"status":"IMPORTED_USER_EVIDENCE","inserted":inserted,
            "unchanged":len(analysis["records"])-inserted,
            "independently_verified":False,"live_feed_connected":False}

def _fingerprint(row):
    # Numeric equality is canonicalized so equivalent decimal representations are idempotent.
    fields = [row["trade_date"],row["market"],row["participant"],
              str(Decimal(row["buy_crore_inr"]).normalize()),
              str(Decimal(row["sell_crore_inr"]).normalize()),
              row["source_name"],row["source_url"] or "",row["verification"]]
    return hashlib.sha256("\x1f".join(fields).encode("utf-8")).hexdigest()

def list_evidence(limit=100):
    limit = max(1,min(int(limit),200))
    with _LOCK, _db() as db:
        rows = db.execute("""SELECT trade_date,market,participant,buy_crore_inr,
            sell_crore_inr,source_name,source_url,verification,imported_at
            FROM flow_evidence ORDER BY trade_date DESC,market,participant LIMIT ?""",(limit,)).fetchall()
        total = db.execute("SELECT COUNT(*) FROM flow_evidence").fetchone()[0]
    today = date.today()
    items=[]
    for row in rows:
        record=dict(row)
        record["net_crore_inr"]=str(Decimal(record["buy_crore_inr"])-Decimal(record["sell_crore_inr"]))
        record["age_days"]=(today-date.fromisoformat(record["trade_date"])).days
        record["freshness"]="RECENT" if record["age_days"]<=3 else "OLD"
        items.append(record)
    return {"records":items,"total":total,"live_feed_connected":False,
            "independently_verified":False,"status":"USER_SUPPLIED_EVIDENCE_ONLY",
            "notice":"No licensed institutional feed. Market scopes may overlap; do not aggregate NSE/BSE with INDIA_COMBINED."}
