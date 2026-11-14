"""SQLite-backed per-provider rolling minute and UTC-day request budgets.

Reservation is atomic across processes sharing one local SQLite database. A reserved
request is charged even if the provider fails; this prevents retry storms.
"""
from datetime import datetime, timezone
from pathlib import Path
import os
import sqlite3

DB_PATH = Path(os.getenv("ATLAS_AI_BUDGET_DB_PATH", "/app/ingestion-data/ai_budgets.sqlite3"))
DEFAULT_LIMITS = {
    "OLLAMA": (120, 10000),
    "GEMINI": (2, 30),
    "GROQ": (5, 100),
    "OPENAI": (0, 0),
    "XAI": (0, 0),
}

def limits(provider):
    if provider not in DEFAULT_LIMITS:
        raise ValueError("UNKNOWN_AI_PROVIDER")
    defaults = DEFAULT_LIMITS[provider]
    result = []
    for suffix, default in zip(("RPM","RPD"),defaults):
        raw = os.getenv("ATLAS_"+provider+"_"+suffix,str(default))
        try:
            value = int(raw)
        except ValueError as exc:
            raise ValueError("INVALID_AI_BUDGET") from exc
        if not 0 <= value <= 100000:
            raise ValueError("INVALID_AI_BUDGET")
        result.append(value)
    return tuple(result)

def _db():
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(str(DB_PATH),timeout=10,isolation_level=None)
    db.execute("PRAGMA busy_timeout=10000")
    db.execute("""CREATE TABLE IF NOT EXISTS ai_request_budget(
        provider TEXT NOT NULL, window TEXT NOT NULL, bucket TEXT NOT NULL,
        count INTEGER NOT NULL, PRIMARY KEY(provider,window,bucket))""")
    return db

def reserve(provider, now=None):
    rpm,rpd=limits(provider)
    if not rpm or not rpd:
        return False
    instant=now or datetime.now(timezone.utc)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("NAIVE_BUDGET_TIME")
    utc=instant.astimezone(timezone.utc)
    minute=utc.strftime("%Y-%m-%dT%H:%M")
    day=utc.strftime("%Y-%m-%d")
    with _db() as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            counts=[]
            for window,bucket in (("minute",minute),("day",day)):
                row=db.execute("""SELECT count FROM ai_request_budget
                    WHERE provider=? AND window=? AND bucket=?""",(provider,window,bucket)).fetchone()
                counts.append(row[0] if row else 0)
            if counts[0]>=rpm or counts[1]>=rpd:
                db.rollback()
                return False
            for window,bucket in (("minute",minute),("day",day)):
                db.execute("""INSERT INTO ai_request_budget(provider,window,bucket,count)
                    VALUES(?,?,?,1) ON CONFLICT(provider,window,bucket)
                    DO UPDATE SET count=count+1""",(provider,window,bucket))
            # Keep recent buckets only. Budget records contain no prompts or credentials.
            db.execute("DELETE FROM ai_request_budget WHERE window='day' AND bucket<?",
                       (utc.date().isoformat(),))
            db.execute("DELETE FROM ai_request_budget WHERE window='minute' AND bucket<?",
                       ((utc.replace(second=0,microsecond=0)).strftime("%Y-%m-%dT%H:%M"),))
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise

def usage(provider, now=None):
    rpm,rpd=limits(provider)
    instant=(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    with _db() as db:
        minute=db.execute("""SELECT count FROM ai_request_budget WHERE
            provider=? AND window='minute' AND bucket=?""",
            (provider,instant.strftime("%Y-%m-%dT%H:%M"))).fetchone()
        day=db.execute("""SELECT count FROM ai_request_budget WHERE
            provider=? AND window='day' AND bucket=?""",
            (provider,instant.strftime("%Y-%m-%d"))).fetchone()
    return {"provider":provider,"rpm_limit":rpm,"rpd_limit":rpd,
            "minute_used":minute[0] if minute else 0,
            "day_used":day[0] if day else 0}
