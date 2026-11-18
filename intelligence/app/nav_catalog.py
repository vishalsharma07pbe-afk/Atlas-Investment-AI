"""Validated, local-first mutual-fund NAV catalog with explicit source provenance."""
from __future__ import annotations
from datetime import datetime, date, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
import os
import sqlite3
import threading
import json

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
    db.execute("""CREATE TABLE IF NOT EXISTS provider_nav_schemes(
      source TEXT NOT NULL, provider_key TEXT NOT NULL, scheme_name TEXT NOT NULL,
      nav TEXT NOT NULL, nav_date TEXT NOT NULL, imported_at TEXT NOT NULL,
      metadata_json TEXT NOT NULL, nav_date_status TEXT NOT NULL DEFAULT 'DECLARED',
      PRIMARY KEY(source,provider_key))""")
    if "nav_date_status" not in {r[1] for r in db.execute("PRAGMA table_info(provider_nav_schemes)")}:
        db.execute("ALTER TABLE provider_nav_schemes ADD COLUMN nav_date_status TEXT NOT NULL DEFAULT 'DECLARED'")
    db.execute("CREATE INDEX IF NOT EXISTS idx_provider_nav_name ON provider_nav_schemes(scheme_name)")
    db.execute("""CREATE TABLE IF NOT EXISTS provider_nav_history(
      source TEXT NOT NULL, provider_key TEXT NOT NULL, nav_date TEXT NOT NULL,
      nav TEXT NOT NULL, imported_at TEXT NOT NULL,
      PRIMARY KEY(source,provider_key,nav_date))""")
    db.execute("""CREATE TABLE IF NOT EXISTS nav_refresh_runs(
      id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL,
      finished_at TEXT NOT NULL, source TEXT NOT NULL, status TEXT NOT NULL,
      parsed INTEGER NOT NULL DEFAULT 0, invalid_rows INTEGER NOT NULL DEFAULT 0,
      inserted_history_rows INTEGER NOT NULL DEFAULT 0, error_code TEXT)""")
    return db

def import_provider_snapshot(records: list[dict], source: str = "UPSTOX_MF_INSTRUMENTS"):
    """Atomically store a validated provider snapshot without inventing AMFI codes."""
    now = datetime.now(timezone.utc).isoformat()
    with _LOCK, _connect() as db:
        inserted_history = 0
        for item in records:
            cursor = db.execute("""INSERT OR IGNORE INTO provider_nav_history
              (source,provider_key,nav_date,nav,imported_at) VALUES(?,?,?,?,?)""",
              (source,item["provider_key"],item["nav_date"],item["nav"],now))
            inserted_history += cursor.rowcount
            db.execute("""INSERT INTO provider_nav_schemes
              (source,provider_key,scheme_name,nav,nav_date,imported_at,metadata_json,nav_date_status)
              VALUES(?,?,?,?,?,?,?,?)
              ON CONFLICT(source,provider_key) DO UPDATE SET
                scheme_name=excluded.scheme_name,nav=excluded.nav,nav_date=excluded.nav_date,
                imported_at=excluded.imported_at,metadata_json=excluded.metadata_json,
                nav_date_status=excluded.nav_date_status
              WHERE excluded.nav_date >= provider_nav_schemes.nav_date""",
              (source,item["provider_key"],item["scheme_name"],item["nav"],item["nav_date"],
               now,json.dumps(item.get("metadata",{}),separators=(",",":"),sort_keys=True),
               item.get("nav_date_status","DECLARED")))
        db.commit()
    return {"status":"IMPORTED","parsed":len(records),"invalid_rows":0,
            "inserted_history_rows":inserted_history,"source":source,
            "live_feed_connected":False}

def record_refresh_run(started_at: str, source: str, status: str, parsed: int = 0,
                       invalid_rows: int = 0, inserted_history_rows: int = 0,
                       error_code: str | None = None):
    finished = datetime.now(timezone.utc).isoformat()
    with _LOCK, _connect() as db:
        db.execute("""INSERT INTO nav_refresh_runs
          (started_at,finished_at,source,status,parsed,invalid_rows,inserted_history_rows,error_code)
          VALUES(?,?,?,?,?,?,?,?)""",(started_at,finished,source,status,parsed,invalid_rows,
                                      inserted_history_rows,error_code))
        db.commit()

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
    pattern = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    with _LOCK, _connect() as db:
        rows = db.execute("""SELECT CAST(scheme_code AS TEXT) AS scheme_code,scheme_name,nav,nav_date,
              source,'DECLARED' AS nav_date_status,imported_at FROM nav_schemes
            WHERE scheme_name LIKE ? ESCAPE '\\' OR CAST(scheme_code AS TEXT) = ?
            UNION ALL
            SELECT provider_key AS scheme_code,scheme_name,nav,nav_date,source,nav_date_status,imported_at
              FROM provider_nav_schemes
            WHERE scheme_name LIKE ? ESCAPE '\\' OR provider_key = ?
            ORDER BY scheme_name LIMIT ?""",
            (pattern,query,pattern,query,limit)).fetchall()
    today = datetime.now(timezone.utc).date()
    now = datetime.now(timezone.utc)
    return {"items": [{**dict(r),
                       "as_of": r["nav_date"] if r["nav_date_status"] == "DECLARED" else r["imported_at"],
                       "freshness_status": ("STALE_NAV" if (today-date.fromisoformat(r["nav_date"])).days>5 else "RECENT_NAV")
                         if r["nav_date_status"] == "DECLARED" else
                         ("CATALOG_RECENT_NAV_DATE_UNVERIFIED" if (now-datetime.fromisoformat(r["imported_at"])).total_seconds()<=129600 else "CATALOG_STALE_NAV_DATE_UNVERIFIED"),
                       "stale": (today - date.fromisoformat(r["nav_date"])).days > 5
                         if r["nav_date_status"] == "DECLARED" else
                         (now-datetime.fromisoformat(r["imported_at"])).total_seconds()>129600}
                      for r in rows], "source": "LOCAL_VALIDATED_IMPORT",
            "live_feed_connected": False, "query": query}

def _returns(rows):
    """Calculate only periods supported by stored dated observations."""
    if len(rows) < 2:
        return {label:None for label in ("1m","3m","6m","1y","3y","5y")}
    latest_day=date.fromisoformat(rows[-1]["nav_date"]);latest=Decimal(rows[-1]["nav"]);result={}
    for label,days in (("1m",30),("3m",90),("6m",180),("1y",365),("3y",1095),("5y",1825)):
        target=latest_day.toordinal()-days
        eligible=[r for r in rows[:-1] if date.fromisoformat(r["nav_date"]).toordinal()<=target]
        if not eligible: result[label]=None;continue
        start=eligible[-1];elapsed=(latest_day-date.fromisoformat(start["nav_date"])).days
        if elapsed<=0 or elapsed>days+14: result[label]=None;continue
        ratio=latest/Decimal(start["nav"])
        value=(ratio**(Decimal("365.25")/Decimal(elapsed))-1) if days>=365 else ratio-1
        result[label]=str((value*100).quantize(Decimal("0.0001")))
    return result

def fund_details(identifier: str):
    if not identifier or len(identifier)>40 or not identifier.replace("-","").isalnum():
        raise ValueError("INVALID_FUND_IDENTIFIER")
    now=datetime.now(timezone.utc)
    with _LOCK, _connect() as db:
        if identifier.isdigit():
            row=db.execute("SELECT * FROM nav_schemes WHERE scheme_code=?",(int(identifier),)).fetchone()
            if not row: raise ValueError("FUND_NOT_FOUND")
            history=db.execute("SELECT nav_date,nav FROM nav_history WHERE scheme_code=? ORDER BY nav_date",(int(identifier),)).fetchall()
            item=dict(row);metadata={};date_status="DECLARED";provider_key=str(item["scheme_code"])
        else:
            row=db.execute("SELECT * FROM provider_nav_schemes WHERE provider_key=? ORDER BY imported_at DESC LIMIT 1",(identifier.upper(),)).fetchone()
            if not row: raise ValueError("FUND_NOT_FOUND")
            history=db.execute("SELECT nav_date,nav FROM provider_nav_history WHERE source=? AND provider_key=? ORDER BY nav_date",(row["source"],row["provider_key"])).fetchall()
            item=dict(row);metadata=json.loads(item["metadata_json"]);date_status=item["nav_date_status"];provider_key=item["provider_key"]
    imported=datetime.fromisoformat(item["imported_at"])
    catalog_age_hours=max(0,(now-imported).total_seconds()/3600)
    returns=_returns([dict(r) for r in history]) if date_status=="DECLARED" else {p:None for p in ("1m","3m","6m","1y","3y","5y")}
    return {
      "identifier":provider_key,"scheme_name":item["scheme_name"],"source":item["source"],
      "scheme_type":metadata.get("scheme_type"),"plan":metadata.get("plan"),
      "dividend_type":metadata.get("dividend_type"),
      "nav":{"value":item["nav"],"declared_date":item["nav_date"] if date_status=="DECLARED" else None,
             "date_status":date_status,"catalog_observed_at":item["imported_at"],
             "catalog_freshness":"RECENT" if catalog_age_hours<=36 else "STALE"},
      "trading_terms":{key:metadata.get(key) for key in (
        "purchase_allowed","redemption_allowed","minimum_purchase_amount","additional_purchase_amount",
        "minimum_redemption_amount","minimum_redemption_quantity","settlement_type")},
      "performance":{"observation_count":len(history),"trailing_returns_percent":returns,
                     "status":"AVAILABLE" if any(v is not None for v in returns.values()) else "COLLECTING_DATED_HISTORY"},
      "portfolio":{"top_holdings":None,"market_cap_allocation":None,"sector_allocation":None,
                   "status":"NOT_PROVIDED_BY_CONNECTED_SOURCE"},
      "costs":{"expense_ratio":None,"exit_load":None,"status":"NOT_PROVIDED_BY_CONNECTED_SOURCE"},
      "rating":{"value":None,"agency":None,"status":"NO_LICENSED_RATING_SOURCE"},
      "research_factors":[
        {"factor":"Returns","status":"AVAILABLE" if any(v is not None for v in returns.values()) else "WAITING_FOR_HISTORY","value":next((v for v in (returns["1y"],returns["6m"],returns["3m"],returns["1m"]) if v is not None),None)},
        {"factor":"Timing / trend","status":"WAITING_FOR_HISTORY","value":None},
        {"factor":"Portfolio quality","status":"MISSING_HOLDINGS_DATA","value":None},
        {"factor":"Market-cap diversification","status":"MISSING_MARKET_CAP_DATA","value":None},
        {"factor":"Cost","status":"MISSING_EXPENSE_RATIO","value":None},
        {"factor":"Independent rating","status":"MISSING_LICENSED_RATING","value":None}],
      "recommendation":{"status":"BLOCKED_INSUFFICIENT_VERIFIED_FACTORS","label":"No recommendation available",
                        "reason":"ATLAS will not rank or recommend this fund until returns, holdings, market-cap allocation, costs and rating evidence are verified."},
      "notice":"Research data only. No purchase, redemption or investment recommendation is generated."
    }

def catalog_status():
    with _LOCK, _connect() as db:
        row = db.execute("""SELECT SUM(total) AS total,MAX(latest) AS latest FROM (
          SELECT COUNT(*) AS total,MAX(nav_date) AS latest FROM nav_schemes
          UNION ALL SELECT COUNT(*),MAX(CASE WHEN nav_date_status='DECLARED' THEN nav_date END)
          FROM provider_nav_schemes)""").fetchone()
        run = db.execute("SELECT * FROM nav_refresh_runs ORDER BY id DESC LIMIT 1").fetchone()
    enabled = os.getenv("ATLAS_MF_NAV_AUTO_REFRESH_ENABLED","false").lower() == "true"
    return {"scheme_count": row["total"] or 0, "latest_nav_date": row["latest"],
            "mode": "AUTOMATIC_DAILY" if enabled else "MANUAL_IMPORT",
            "automatic_collection_enabled": enabled,
            "blocker": None if enabled else "AUTOMATIC_REFRESH_DISABLED",
            "source": "UPSTOX_MF_INSTRUMENTS" if enabled else "AMFI_MANUAL_DOWNLOAD",
            "last_refresh_at": run["finished_at"] if run else None,
            "last_refresh_status": run["status"] if run else "NEVER_RUN",
            "last_refresh_error": run["error_code"] if run else None,
            "last_refresh_imported": run["parsed"] if run else 0,
            "last_refresh_rejected": run["invalid_rows"] if run else 0,
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
    return {"items": [dict(r) for r in rows],
            "automatic_collection_enabled": os.getenv("ATLAS_MF_NAV_AUTO_REFRESH_ENABLED","false").lower() == "true"}
