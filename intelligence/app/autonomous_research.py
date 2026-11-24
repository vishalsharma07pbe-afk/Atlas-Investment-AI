"""Persisted, read-only research snapshots built from existing validated engines.

Public market/fund observations only: never store owner holdings, tokens, or AI prompts.
A failed section does not replace its last good snapshot or masquerade as fresh data.
"""
from __future__ import annotations

import asyncio
from contextlib import closing
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
import json
import os
from pathlib import Path
import sqlite3
from urllib.parse import urlencode

from .market_client import backend_json
from .screener import screen
from .mutual_fund_recommendations import CATEGORIES, dashboard
from . import automatic_ai_review, watch_outcomes, automatic_company_evidence, automatic_institutional, automatic_news, portfolio_thesis, automatic_strategy_validation, research_reliability

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
    # Attach registry identity, not ticker-based guesses, for company evidence.
    registry = {row["id"]: row for row in instruments if row.get("active") is True
                and row.get("listing_status") == "ACTIVE" and row.get("series") == "EQ"}
    for group in result["horizons"].values():
        for candidate in group["candidates"]:
            record = registry.get(candidate["id"])
            if record and record.get("symbol") == candidate["symbol"] and record.get("exchange") == candidate["exchange"]:
                candidate["isin"] = record.get("isin")
    result["notice"] = ("Automatically refreshed daily observations from a bounded registry sample. "
                        "Not live intraday signals, full-exchange rankings, or recommendations.")
    return result


def fund_snapshot(category):
    result = dashboard(category, 60, "MODERATE")
    # Keep the existing strict ranking methodology; store only the result fields
    # needed by the overview, not the catalog or individual excluded records.
    return {key: result[key] for key in (
        "category", "coverage", "top_performers", "growth_outlook",
        "recommendation_status", "blockers", "notice", "filters", "historical_coverage")}


def refresh_once(market_loader=market_snapshot, fund_loader=fund_snapshot):
    """Independent bounded sections, with no browser or external AI requirement."""
    for section in SECTIONS:
        try:
            result = market_loader(section) if section in ("NSE", "BSE") else fund_loader(section)
            _save(section, result)
        except Exception:
            # Do not persist provider errors, URLs, credentials or traceback text.
            _save(section)


def _published_evidence_current(section, result, today):
    """Reapply observation-date limits at read time, not just generation time.

    The entire section becomes stale if any published watch fails its original
    date gate. This avoids silently reranking an incomplete persisted sample.
    Empty successful samples remain READY; READY is processing, not coverage.
    """
    def fresh(value, minimum, maximum):
        return minimum <= (today-date.fromisoformat(value)).days <= maximum

    if section in ("NSE", "BSE"):
        for key in ("top_gainers", "top_losers", "momentum_leaders"):
            if any(not fresh(item["as_of"], 1, 4) for item in result.get(key, [])):
                return False
        for group in result.get("horizons", {}).values():
            if any(not fresh(item["as_of"], 1, 4) for item in group.get("candidates", [])):
                return False
    else:
        history = result.get("historical_coverage") or {}
        for key in ("items", "risk_adjusted_items"):
            if any(not fresh(item["nav_date"], 0, 7) or item["nav_date"] != history.get("comparison_date")
                   for item in history.get(key, [])):
                return False
        # The current strict catalog cannot qualify recommendations without
        # evidence, but recheck dates defensively if qualified picks are stored.
        for key in ("top_performers", "growth_outlook"):
            if any(not fresh(item["fund"]["nav_date"], 0, 7) for item in result.get(key, [])):
                return False
    return True


def read_snapshot(include_ai=True):
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
        error_code = row["error_code"]
        try:
            result = json.loads(row["payload"]) if row["payload"] else None
            if result is not None and not isinstance(result, dict):
                raise ValueError("INVALID_SNAPSHOT")
            age = (current - datetime.fromisoformat(row["generated_at"])).total_seconds() if row["generated_at"] else None
            stale = age is None or age < 0 or age > max(3600, interval * 3)
            status = "DISABLED" if not enabled else "FAILED" if row["status"] == "FAILED" else "STALE" if stale else "READY"
            if status == "READY":
                if result is None:
                    raise ValueError("MISSING_SNAPSHOT")
                if not _published_evidence_current(section, result, current.astimezone(ZoneInfo("Asia/Kolkata")).date()):
                    status = "STALE"
                    error_code = "UNDERLYING_OBSERVATION_STALE"
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
            result = None
            status = "FAILED" if enabled else "DISABLED"
            error_code = "INVALID_STORED_RESEARCH_SNAPSHOT"
        sections.append({"section": section, "status": status,
                         "generated_at": row["generated_at"], "attempted_at": row["attempted_at"],
                         "result": result, "error_code": error_code})
    snapshot = {"enabled": enabled, "interval_seconds": interval, "sections": sections,
            "scope": "PUBLIC_MARKET_RESEARCH_ONLY",
            "notice": "Snapshot time is not the underlying observation time. Missing evidence never becomes a recommendation."}
    if include_ai:
        try:
            snapshot["strategy_validation"] = automatic_strategy_validation.read(_connect) if enabled else {"status":"DISABLED"}
        except (ValueError, OSError, sqlite3.Error):
            snapshot["strategy_validation"] = {"status":"UNAVAILABLE"}
        try:
            snapshot["institutional_activity"] = automatic_institutional.read(_connect) if enabled else {"status":"AUTOMATION_DISABLED"}
        except (ValueError, OSError, sqlite3.Error):
            snapshot["institutional_activity"] = {"status":"UNAVAILABLE"}
        try:
            automatic_company_evidence.attach(snapshot, _connect)
        except (ValueError, OSError, sqlite3.Error):
            snapshot["automatic_company_status"] = "UNAVAILABLE"
        try:
            automatic_news.attach(snapshot, _connect)
        except (ValueError, OSError, sqlite3.Error):
            snapshot["automatic_news_status"] = "UNAVAILABLE"
        try:
            snapshot["research_reliability"] = research_reliability.read(_connect,current) if enabled else {"status":"DISABLED"}
        except (ValueError, OSError, sqlite3.Error):
            snapshot["research_reliability"] = {"status":"UNAVAILABLE"}
        research_reliability.attach(snapshot,snapshot["research_reliability"],current.astimezone(ZoneInfo("Asia/Kolkata")).date())
        try:
            return automatic_ai_review.attach(snapshot, _connect)
        except (ValueError, OSError, sqlite3.Error):
            snapshot["automatic_ai_status"] = "UNAVAILABLE"
    return snapshot


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
                try:
                    await asyncio.to_thread(automatic_institutional.refresh, _connect)
                except Exception:
                    pass  # Aggregate flows never block other research sections.
                await asyncio.to_thread(refresh_once)
                snapshot = await asyncio.to_thread(read_snapshot, False)
                try:
                    await asyncio.to_thread(watch_outcomes.refresh, snapshot, _connect)
                except Exception:
                    pass  # Outcome collection cannot block AI or deterministic research.
                try:
                    await asyncio.to_thread(automatic_company_evidence.refresh, snapshot, _connect)
                except Exception:
                    pass  # Company evidence must not block the existing research engine.
                try:
                    await asyncio.to_thread(automatic_news.refresh, snapshot, _connect)
                except Exception:
                    pass  # Provider news failure must not block research.
                try:
                    await asyncio.to_thread(portfolio_thesis.refresh)
                except Exception:
                    pass  # Private company research is independent of public discovery.
                try:
                    await asyncio.to_thread(automatic_strategy_validation.refresh, snapshot, _connect)
                except Exception:
                    pass  # Validation cannot block other research.
                await asyncio.to_thread(automatic_ai_review.refresh, snapshot, _connect)
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
