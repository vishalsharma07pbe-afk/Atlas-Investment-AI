"""Validated, local-first mutual-fund NAV catalog. No network fetch or licensing assumption."""
from datetime import datetime, date, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
import os
import sqlite3
import threading

DB_PATH = Path(os.getenv("ATLAS_NAV_DB_PATH", "/app/nav-data/catalog.sqlite3"))
_LOCK = threading.RLock()
MAX_BYTES = 8_000_000
MAX_ROWS = 40_000

def parse_nav(text: str):
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise ValueError("NAV_FILE_TOO_LARGE")
    records = {}
    invalid = 0
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(";")]
        if len(parts) not in (6, 8) or not parts[0].isdigit():
            continue
        try:
            code = int(parts[0])
            if code <= 0 or code > 999999999:
                raise ValueError("invalid code")
            name = parts[3]
            if not name or len(name) > 300:
                raise ValueError("invalid name")
            nav = Decimal(parts[-2])
            if not nav.is_finite() or nav <= 0 or nav > Decimal("1000000000"):
                raise ValueError("invalid NAV")
            observed = datetime.strptime(parts[-1], "%d-%b-%Y").date()
            if observed > datetime.now(timezone.utc).date():
                raise ValueError("future NAV")
            if code in records:
                raise ValueError("duplicate scheme")
            records[code] = (code, name, str(nav), observed.isoformat(), parts[1], parts[2])
            if len(records) > MAX_ROWS:
                raise ValueError("NAV_ROW_LIMIT")
        except (ValueError, InvalidOperation, OverflowError):
            invalid += 1
    if not records:
        raise ValueError("NO_VALID_NAV_RECORDS")
    return list(records.values()), invalid

def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH), timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS nav_schemes(
      scheme_code INTEGER PRIMARY KEY, scheme_name TEXT NOT NULL, nav TEXT NOT NULL,
      nav_date TEXT NOT NULL, isin_growth TEXT, isin_reinvestment TEXT,
      imported_at TEXT NOT NULL, source TEXT NOT NULL)""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_nav_scheme_name ON nav_schemes(scheme_name)")
    db.execute("""CREATE TABLE IF NOT EXISTS nav_history(
      scheme_code INTEGER NOT NULL, nav_date TEXT NOT NULL, nav TEXT NOT NULL,
      source TEXT NOT NULL, imported_at TEXT NOT NULL,
      PRIMARY KEY(scheme_code, nav_date))""")
    db.execute("""CREATE TABLE IF NOT EXISTS nav_import_audit(
      id INTEGER PRIMARY KEY AUTOINCREMENT, imported_at TEXT NOT NULL,
      source TEXT NOT NULL, parsed INTEGER NOT NULL, invalid_rows INTEGER NOT NULL,
      inserted_history_rows INTEGER NOT NULL)""")
    return db

def import_snapshot(text: str, source: str = "AMFI_MANUAL_DOWNLOAD"):
    records, invalid = parse_nav(text)
    now = datetime.now(timezone.utc).isoformat()
    with _LOCK, _connect() as db:
        inserted_history = 0
        for code, name, nav, day, isin1, isin2 in records:
            cursor = db.execute("""INSERT OR IGNORE INTO nav_history
                (scheme_code,nav_date,nav,source,imported_at) VALUES(?,?,?,?,?)""",
                (code, day, nav, source, now))
            inserted_history += cursor.rowcount
            db.execute("""INSERT INTO nav_schemes VALUES(?,?,?,?,?,?,?,?)
              ON CONFLICT(scheme_code) DO UPDATE SET scheme_name=excluded.scheme_name,
              nav=excluded.nav, nav_date=excluded.nav_date,
              isin_growth=excluded.isin_growth, isin_reinvestment=excluded.isin_reinvestment,
              imported_at=excluded.imported_at, source=excluded.source
              WHERE excluded.nav_date >= nav_schemes.nav_date""",
              (code, name, nav, day, isin1, isin2, now, source))
        db.execute("""INSERT INTO nav_import_audit
            (imported_at,source,parsed,invalid_rows,inserted_history_rows)
            VALUES(?,?,?,?,?)""",(now,source,len(records),invalid,inserted_history))
        db.commit()
    return {"status": "IMPORTED", "parsed": len(records), "invalid_rows": invalid,
            "inserted_history_rows": inserted_history,
            "source": source, "live_feed_connected": False}

def search_schemes(query: str = "", limit: int = 30):
    if len(query) > 100:
        raise ValueError("QUERY_TOO_LONG")
    limit = max(1, min(limit, 100))
    with _LOCK, _connect() as db:
        rows = db.execute("""SELECT * FROM nav_schemes
            WHERE scheme_name LIKE ? ESCAPE '\\' OR CAST(scheme_code AS TEXT) = ?
            ORDER BY scheme_name LIMIT ?""",
            ("%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%", query, limit)).fetchall()
    today = datetime.now(timezone.utc).date()
    return {"items": [{**dict(r), "stale": (today - date.fromisoformat(r["nav_date"])).days > 5}
                      for r in rows], "source": "LOCAL_VALIDATED_IMPORT",
            "live_feed_connected": False, "query": query}

def catalog_status():
    with _LOCK, _connect() as db:
        row = db.execute("SELECT COUNT(*) AS total, MAX(nav_date) AS latest FROM nav_schemes").fetchone()
    return {"scheme_count": row["total"], "latest_nav_date": row["latest"],
            "mode": "MANUAL_IMPORT", "automatic_collection_enabled": False,
            "blocker": "AUTOMATED_SOURCE_USAGE_RIGHTS_NOT_VERIFIED",
            "live_feed_connected": False}

def scheme_history(scheme_code: int, limit: int = 365):
    """Validated local observations only. No inferred NAVs or ratings."""
    if not 1 <= scheme_code <= 999999999:
        raise ValueError("INVALID_SCHEME_CODE")
    if not 1 <= limit <= 2000:
        raise ValueError("INVALID_LIMIT")
    with _LOCK, _connect() as db:
        rows = db.execute("""SELECT nav_date, nav, source, imported_at FROM nav_history
            WHERE scheme_code=? ORDER BY nav_date DESC LIMIT ?""",
            (scheme_code, limit)).fetchall()
    items = [dict(r) for r in reversed(rows)]
    performance = None
    if len(items) >= 2:
        start = Decimal(items[0]["nav"])
        end = Decimal(items[-1]["nav"])
        performance = str(((end / start) - 1) * 100)
    return {"scheme_code": scheme_code, "items": items,
            "observed_period_return_percent": performance,
            "verified_rating": None, "live_feed_connected": False,
            "notice": "Returns use only imported observation dates; not annualized or adjusted for distributions."}

def import_audit(limit: int = 20):
    if not 1 <= limit <= 100:
        raise ValueError("INVALID_LIMIT")
    with _LOCK, _connect() as db:
        rows = db.execute("SELECT * FROM nav_import_audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return {"items": [dict(r) for r in rows], "automatic_collection_enabled": False}
