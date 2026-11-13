"""Persistent, explicitly user-supplied global news evidence; no automated scraping."""
from datetime import datetime, timezone
from pathlib import Path
import os
import sqlite3
import threading
from urllib.parse import urlsplit

from .news_events import NewsRequest, analyze_news

DB_PATH = Path(os.getenv("ATLAS_NEWS_DB_PATH", "/app/news-data/events.sqlite3"))
_LOCK = threading.RLock()

def _db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH), timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS news_events (
      source_url TEXT NOT NULL, published_at TEXT NOT NULL,
      headline TEXT NOT NULL, source_name TEXT NOT NULL, symbol TEXT,
      geography TEXT NOT NULL, event_type TEXT NOT NULL,
      sentiment TEXT NOT NULL, sentiment_method TEXT NOT NULL,
      imported_at TEXT NOT NULL,
      PRIMARY KEY (source_url,published_at))""")
    db.execute("CREATE INDEX IF NOT EXISTS news_events_date_idx ON news_events(published_at DESC)")
    return db

def _url(url):
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("SOURCE_URL_MUST_BE_PUBLIC_HTTPS")
    hostname = parts.hostname.lower().rstrip(".")
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith((".local", ".internal")):
        raise ValueError("SOURCE_URL_MUST_BE_PUBLIC_HTTPS")
    return url

def import_news(request: NewsRequest):
    # Reject entire batch on duplicates/conflicts. Do not fetch URLs or trust their contents.
    analyzed = analyze_news(request.events, request.max_age_hours)
    records = []
    for e in request.events:
        url = _url(e.source_url)
        records.append((url, e.published_at.isoformat(), e.headline, e.source_name,
                        e.symbol, e.geography, e.event_type, e.sentiment, e.sentiment_method))
    now = datetime.now(timezone.utc).isoformat()
    with _LOCK, _db() as db:
        for row in records:
            previous = db.execute("""SELECT headline,source_name,symbol,geography,event_type,
                sentiment,sentiment_method FROM news_events WHERE source_url=? AND published_at=?""",
                row[:2]).fetchone()
            if previous is not None and tuple(previous) != row[2:]:
                raise ValueError("CONFLICTING_NEWS_EVIDENCE")
        inserted = 0
        for row in records:
            cursor = db.execute("""INSERT OR IGNORE INTO news_events
                (source_url,published_at,headline,source_name,symbol,geography,event_type,
                 sentiment,sentiment_method,imported_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (*row, now))
            inserted += cursor.rowcount
        db.commit()
    return {"status": "USER_SUPPLIED_NEWS_STORED", "inserted": inserted,
            "duplicates": len(records)-inserted, "analyzed": analyzed["event_count"],
            "automatic_feed_connected": False, "independently_verified": False}

def list_news(limit=50, max_age_hours=72, geography=None):
    if not 1 <= limit <= 200 or not 1 <= max_age_hours <= 720:
        raise ValueError("INVALID_NEWS_QUERY")
    if geography and geography not in {"INDIA","GLOBAL","US","EUROPE","ASIA_OTHER","OTHER"}:
        raise ValueError("INVALID_GEOGRAPHY")
    with _LOCK, _db() as db:
        if geography:
            rows = db.execute("SELECT * FROM news_events WHERE geography=? ORDER BY published_at DESC LIMIT ?",
                              (geography,limit)).fetchall()
        else:
            rows = db.execute("SELECT * FROM news_events ORDER BY published_at DESC LIMIT ?", (limit,)).fetchall()
    now = datetime.now(timezone.utc)
    events=[]
    for row in rows:
        item=dict(row)
        age=(now-datetime.fromisoformat(item["published_at"])).total_seconds()/3600
        item["age_hours"]=round(age,2)
        item["freshness"]="FRESH" if 0 <= age <= max_age_hours else "STALE"
        item["independently_verified"]=False
        events.append(item)
    return {"status":"USER_SUPPLIED_NEWS_EVIDENCE", "events":events,
            "event_count":len(events), "fresh_count":sum(x["freshness"]=="FRESH" for x in events),
            "automatic_feed_connected":False, "notice":"Stored user-labelled evidence; URLs and claims not independently verified."}
