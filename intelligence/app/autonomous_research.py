"""Persisted, read-only research snapshots built from existing validated engines.

Public market/fund observations only: never store owner holdings, tokens, or AI prompts.
A failed section does not replace its last good snapshot or masquerade as fresh data.
"""
from __future__ import annotations

import asyncio
from contextlib import closing
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import json
import os
from pathlib import Path
import sqlite3
from urllib.parse import urlencode

from .market_client import backend_json
from .screener import screen
from .mutual_fund_recommendations import CATEGORIES, dashboard

SECTIONS = ("NSE", "BSE", *CATEGORIES)
DEFAULT_INTERVAL = 900


def config():
    enabled = os.getenv("ATLAS_AUTONOMOUS_RESEARCH_ENABLED", "false").lower() == "true"
    try:
        interval = int(os.getenv("ATLAS_AUTONOMOUS_RESEARCH_INTERVAL_SECONDS", str(DEFAULT_INTERVAL)))
        if not 300 <= interval <= 86400:
            raise ValueError()
    except ValueError:
        return False, DEFAULT_INTERVAL
    return enabled, interval


def now():
    return datetime.now(timezone.utc)


def _connect():
    path = Path(os.getenv("ATLAS_RESEARCH_SNAPSHOT_DB", "/app/ingestion-data/research_snapshots.sqlite3"))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS research_sections(
        section TEXT PRIMARY KEY, generated_at TEXT, attempted_at TEXT NOT NULL,
        status TEXT NOT NULL, payload TEXT, error_code TEXT)""")
    return db


def _save(section, result=None):
    stamp = now().isoformat()
    with closing(_connect()) as db, db:
        if result is None:
            db.execute("""INSERT INTO research_sections(section,attempted_at,status,error_code)
                VALUES(?,?,'FAILED','RESEARCH_REFRESH_FAILED')
                ON CONFLICT(section) DO UPDATE SET attempted_at=excluded.attempted_at,
                status=excluded.status,error_code=excluded.error_code""", (section, stamp))
        else:
            db.execute("""INSERT INTO research_sections VALUES(?,?,?,'READY',?,NULL)
                ON CONFLICT(section) DO UPDATE SET generated_at=excluded.generated_at,
                attempted_at=excluded.attempted_at,status=excluded.status,
                payload=excluded.payload,error_code=NULL""",
                (section, stamp, stamp, json.dumps(result, default=str, allow_nan=False)))


def market_snapshot(exchange):
    instruments = backend_json("/api/v1/instruments?" + urlencode({"limit": 60, "exchange": exchange}))
    if not isinstance(instruments, list):
        raise ValueError("INVALID_REGISTRY")
    # Do not include inactive or non-equity listings in discovery.
    instruments = [row for row in instruments if row.get("active", True)
                   and row.get("listing_status", "ACTIVE") == "ACTIVE"
                   and row.get("instrument_type", "EQUITY") in ("EQUITY", "EQ", "STOCK")]
    today = now().astimezone(ZoneInfo("Asia/Kolkata")).date()
    # This pipeline deliberately excludes the current session, which may still
    # be forming. Retain the real underlying candle dates in every observation.
    def completed_history(instrument_id):
        payload = backend_json(f"/api/v1/market-data/instruments/{instrument_id}/candles?limit=250")
        return {**payload, "candles": [row for row in payload["candles"]
                if str(row["trade_date"]) < today.isoformat()]}
    result = screen(instruments, completed_history, as_of=today,
                    universe_limit=60, max_age_days=4, include_horizons=True)
    result["notice"] = ("Automatically refreshed daily observations from a bounded registry sample. "
                        "Not live intraday signals, full-exchange rankings, or recommendations.")
    return result


def fund_snapshot(category):
    result = dashboard(category, 60, "MODERATE")
    # Keep the existing strict ranking methodology; store only the result fields
    # needed by the overview, not the catalog or individual excluded records.
    return {key: result[key] for key in (
        "category", "coverage", "top_performers", "growth_outlook",
        "recommendation_status", "blockers", "notice", "filters")}


def refresh_once(market_loader=market_snapshot, fund_loader=fund_snapshot):
    """Independent bounded sections, with no browser or external AI requirement."""
    for section in SECTIONS:
        try:
            result = market_loader(section) if section in ("NSE", "BSE") else fund_loader(section)
            _save(section, result)
        except Exception:
            # Do not persist provider errors, URLs, credentials or traceback text.
            _save(section)


def read_snapshot():
    enabled, interval = config()
    current = now()
    with closing(_connect()) as db:
        records = {row["section"]: row for row in db.execute("SELECT * FROM research_sections")}
    sections = []
    for section in SECTIONS:
        row = records.get(section)
        if row is None:
            sections.append({"section": section, "status": "PENDING" if enabled else "DISABLED",
                             "generated_at": None, "attempted_at": None, "result": None})
            continue
        age = (current - datetime.fromisoformat(row["generated_at"])).total_seconds() if row["generated_at"] else None
        stale = age is None or age < 0 or age > max(3600, interval * 3)
        status = "FAILED" if row["status"] == "FAILED" else "STALE" if stale else "READY"
        sections.append({"section": section, "status": status,
                         "generated_at": row["generated_at"], "attempted_at": row["attempted_at"],
                         "result": json.loads(row["payload"]) if row["payload"] else None,
                         "error_code": row["error_code"]})
    return {"enabled": enabled, "interval_seconds": interval, "sections": sections,
            "scope": "PUBLIC_MARKET_RESEARCH_ONLY",
            "notice": "Snapshot time is not the underlying observation time. Missing evidence never becomes a recommendation."}


class ResearchScheduler:
    def __init__(self):
        self.task = None
        self.stopping = None

    async def start(self):
        enabled, interval = config()
        if enabled and self.task is None:
            self.stopping = asyncio.Event()
            self.task = asyncio.create_task(self._loop(interval))

    async def _loop(self, interval):
        while not self.stopping.is_set():
            try:
                await asyncio.to_thread(refresh_once)
            except Exception:
                # Storage failures must not terminate future attempts.
                pass
            try:
                await asyncio.wait_for(self.stopping.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    async def stop(self):
        if self.task is not None:
            self.stopping.set()
            # A thread cannot be forcibly cancelled safely. Wait for the current
            # bounded pass, allowing the container shutdown timeout to apply.
            await self.task
            self.task = None


scheduler = ResearchScheduler()
