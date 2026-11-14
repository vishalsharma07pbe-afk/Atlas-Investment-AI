"""Provider-independent, strictly validated daily OHLCV observations with source provenance."""
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
import os
import re
import sqlite3
import threading

DB_PATH = Path(os.getenv("ATLAS_OHLCV_DB_PATH", "/app/ingestion-data/ohlcv.sqlite3"))
_LOCK = threading.RLock()
SYMBOL = re.compile(r"^[A-Z0-9._&-]{1,40}$")
SOURCE = re.compile(r"^[A-Z][A-Z0-9_]{1,39}$")

def _db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH), timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS ohlcv_daily (
        symbol TEXT NOT NULL, market TEXT NOT NULL, session_date TEXT NOT NULL,
        source TEXT NOT NULL, open TEXT NOT NULL, high TEXT NOT NULL,
        low TEXT NOT NULL, close TEXT NOT NULL, volume INTEGER NOT NULL,
        imported_at TEXT NOT NULL, PRIMARY KEY(symbol,market,session_date,source))""")
    db.execute("""CREATE TABLE IF NOT EXISTS ohlcv_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL,
        market TEXT NOT NULL, source TEXT NOT NULL, inserted INTEGER NOT NULL,
        unchanged INTEGER NOT NULL, recorded_at TEXT NOT NULL)""")
    return db

def _positive(value):
    try:
        n = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("INVALID_OHLC_PRICE") from exc
    if not n.is_finite() or n <= 0:
        raise ValueError("INVALID_OHLC_PRICE")
    return n

def validate(row):
    if not isinstance(row, dict) or set(row) != {"date","open","high","low","close","volume"}:
        raise ValueError("INVALID_CANDLE_FIELDS")
    try:
        day = date.fromisoformat(row["date"])
    except (TypeError, ValueError) as exc:
        raise ValueError("INVALID_SESSION_DATE") from exc
    if day > datetime.now(timezone.utc).date():
        raise ValueError("FUTURE_SESSION_DATE")
    prices = {k:_positive(row[k]) for k in ("open","high","low","close")}
    if prices["high"] < max(prices["open"],prices["close"],prices["low"]) or prices["low"] > min(prices["open"],prices["close"]):
        raise ValueError("INCONSISTENT_OHLC")
    volume = row["volume"]
    if type(volume) is not int or volume < 0 or volume > 10**15:
        raise ValueError("INVALID_VOLUME")
    return (day.isoformat(), *(str(prices[k]) for k in ("open","high","low","close")), volume)

def import_candles(symbol, market, source, rows):
    if not isinstance(symbol,str) or not SYMBOL.fullmatch(symbol):
        raise ValueError("INVALID_SYMBOL")
    if market not in ("NSE","BSE","US"):
        raise ValueError("INVALID_MARKET")
    if not isinstance(source,str) or not SOURCE.fullmatch(source):
        raise ValueError("INVALID_SOURCE")
    if not isinstance(rows,list) or not 1 <= len(rows) <= 5000:
        raise ValueError("INVALID_BATCH_SIZE")
    validated = [validate(row) for row in rows]
    if len({row[0] for row in validated}) != len(validated):
        raise ValueError("DUPLICATE_SESSION_DATE")
    now = datetime.now(timezone.utc).isoformat()
    with _LOCK, _db() as db:
        # No overwrite: divergent observations require reconciliation, never silent replacement.
        for day, op, hi, lo, cl, vol in validated:
            previous = db.execute("""SELECT open,high,low,close,volume FROM ohlcv_daily
                WHERE symbol=? AND market=? AND session_date=? AND source=?""",
                (symbol,market,day,source)).fetchone()
            if previous and tuple(previous) != (op,hi,lo,cl,vol):
                raise ValueError("CONFLICTING_SOURCE_OBSERVATION")
        inserted = 0
        for day, op, hi, lo, cl, vol in validated:
            cursor = db.execute("""INSERT OR IGNORE INTO ohlcv_daily
                (symbol,market,session_date,source,open,high,low,close,volume,imported_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",(symbol,market,day,source,op,hi,lo,cl,vol,now))
            inserted += cursor.rowcount
        db.execute("""INSERT INTO ohlcv_audit(symbol,market,source,inserted,unchanged,recorded_at)
            VALUES(?,?,?,?,?,?)""",(symbol,market,source,inserted,len(validated)-inserted,now))
        db.commit()
    return {"status":"IMPORTED","inserted":inserted,"unchanged":len(validated)-inserted,
            "source":source,"live_feed_connected":False}

def history(symbol, market, limit=365):
    if not isinstance(symbol,str) or not SYMBOL.fullmatch(symbol) or market not in ("NSE","BSE","US"):
        raise ValueError("INVALID_INSTRUMENT")
    if type(limit) is not int or not 1 <= limit <= 2000:
        raise ValueError("INVALID_LIMIT")
    with _LOCK, _db() as db:
        rows = db.execute("""SELECT * FROM ohlcv_daily WHERE symbol=? AND market=?
            ORDER BY session_date DESC, source LIMIT ?""",(symbol,market,limit)).fetchall()
    items = [dict(row) for row in reversed(rows)]
    latest = max((x["session_date"] for x in items),default=None)
    return {"items":items,"latest_session_date":latest,"stale_calendar_days":
            (datetime.now(timezone.utc).date()-date.fromisoformat(latest)).days if latest else None,
            "live_feed_connected":False,"notice":"Validated imported observations, not a live feed."}
