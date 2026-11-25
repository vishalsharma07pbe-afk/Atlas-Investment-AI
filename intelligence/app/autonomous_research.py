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
from . import automatic_deals, fund_portfolios, fund_disclosures, research_jobs, research_calendar, daily_briefing, automatic_ai_review, watch_outcomes, automatic_company_evidence, automatic_institutional, automatic_news, portfolio_thesis, automatic_strategy_validation, research_reliability

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
    instruments = backend_json("/api/v1/market-data/discovery-universe?" + urlencode({"exchange": exchange}))
    if not isinstance(instruments, list) or len(instruments)>200:
        raise ValueError("INVALID_REGISTRY")
    if any(not isinstance(row,dict) or row.get("exchange")!=exchange or row.get("active") is not True
           or row.get("listing_status")!="ACTIVE" or row.get("series")!="EQ"
           or row.get("instrument_type") not in ("EQUITY","EQ","STOCK")
           or type(row.get("id")) is not int or row["id"]<=0 for row in instruments):
        raise ValueError("INVALID_DISCOVERY_IDENTITY")
    ids=[row["id"] for row in instruments]
    if len(set(ids))!=len(ids):
        raise ValueError("DUPLICATE_DISCOVERY_IDENTITY")
    counts={row.get("recent_registry_count") for row in instruments}
    recent_count=next(iter(counts)) if len(counts)==1 else 0
    if instruments and (type(recent_count) is not int or recent_count<len(instruments)):
        raise ValueError("INVALID_DISCOVERY_COVERAGE")
    today = now().astimezone(ZoneInfo("Asia/Kolkata")).date()
    sessions={row.get("expected_session") for row in instruments}
    if len(sessions)>1:
        raise ValueError("INCONSISTENT_DISCOVERY_CALENDAR")
    expected=next(iter(sessions),None)
    expected_session=date.fromisoformat(expected) if expected is not None else None
    if expected_session is not None and not 1<=(today-expected_session).days<=14:
        raise ValueError("INVALID_DISCOVERY_CALENDAR")
    matching_counts={row.get("expected_session_count") for row in instruments}
    matching=next(iter(matching_counts)) if len(matching_counts)==1 else None
    if expected_session is not None and (type(matching) is not int or not 0<=matching<=recent_count):
        raise ValueError("INVALID_SESSION_COVERAGE")
    histories={identifier:[] for identifier in ids}
    # At most ten local batch requests per exchange; no provider requests.
    for offset in range(0,len(ids),20):
        batch=ids[offset:offset+20]
        rows=backend_json("/api/v1/market-data/discovery-candles?"+urlencode({"exchange":exchange,"ids":batch},doseq=True))
        if not isinstance(rows,list) or len(rows)>len(batch)*250:
            raise ValueError("INVALID_DISCOVERY_HISTORY")
        for row in rows:
            if not isinstance(row,dict) or type(row.get("instrument_id")) is not int or row["instrument_id"] not in batch:
                raise ValueError("DISCOVERY_HISTORY_IDENTITY_MISMATCH")
            if str(row["trade_date"])<today.isoformat():
                histories[row["instrument_id"]].append(row)
        if any(len(histories[i])>250 for i in batch):
            raise ValueError("DISCOVERY_HISTORY_LIMIT_EXCEEDED")
    result = screen(instruments, lambda identifier:{"candles":histories[identifier]}, as_of=today,
                    universe_limit=200, max_age_days=4, include_horizons=True, batch_loaded=True, expected_session=expected_session)
    result["discovery_coverage"]={"recent_registry_count":recent_count,"selected_count":len(ids),
        "selection_limit":200,"selection_method":"EXPECTED_SESSION_THEN_DAILY_TRADED_VALUE",
        "expected_session_count":matching if expected_session else None,
        "history_batch_size":20,"calendar_status":"PUBLISHED_SESSION" if expected_session else "CALENDAR_UNVERIFIED",
        "expected_session":expected,"calendar_checked_on":today.isoformat()}
    # Attach registry identity, not ticker-based guesses, for company evidence.
    registry = {row["id"]: row for row in instruments if row.get("active") is True
                and row.get("listing_status") == "ACTIVE" and row.get("series") == "EQ"}
    for group in result["horizons"].values():
        for candidate in group["candidates"]:
            record = registry.get(candidate["id"])
            if record and record.get("symbol") == candidate["symbol"] and record.get("exchange") == candidate["exchange"]:
                candidate["isin"] = record.get("isin")
    result["notice"] = ("Automatically refreshed daily observations from up to 200 recent active cash equities per exchange, prioritizing the expected completed session, then latest daily traded value. "
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
        coverage=result.get("discovery_coverage") or {}
        expected=coverage.get("expected_session")
        # A published session assertion belongs only to its checked IST date.
        if expected is not None and coverage.get("calendar_checked_on")!=today.isoformat():
            return False
        if expected is not None and not fresh(expected,1,4):
            return False
        def equity_fresh(item):
            return fresh(item["as_of"],1,4) and (expected is None or item["as_of"]==expected)
        for key in ("top_gainers", "top_losers", "momentum_leaders"):
            if any(not equity_fresh(item) for item in result.get(key, [])):
                return False
        for group in result.get("horizons", {}).values():
            if any(not equity_fresh(item) for item in group.get("candidates", [])):
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
            snapshot["strategy_validation"] = automatic_strategy_validation.read(_connect,current,snapshot=snapshot) if enabled else {"status":"DISABLED"}
        except (ValueError, OSError, sqlite3.Error):
            snapshot["strategy_validation"] = {"status":"UNAVAILABLE"}
        try:
            snapshot["institutional_activity"] = automatic_institutional.read(_connect) if enabled else {"status":"AUTOMATION_DISABLED"}
        except (ValueError, OSError, sqlite3.Error):
            snapshot["institutional_activity"] = {"status":"UNAVAILABLE"}
        try:
            automatic_deals.attach(snapshot,_connect,current)
        except (ValueError,OSError,sqlite3.Error):
            snapshot["institutional_activity"]["deal_reports"]={"status":"UNAVAILABLE"}
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
            automatic_ai_review.attach(snapshot, _connect)
        except (ValueError, OSError, sqlite3.Error):
            snapshot["automatic_ai_status"] = "UNAVAILABLE"
        research_reliability.attach_conclusions(snapshot)
        snapshot["daily_briefing"] = daily_briefing.summarize(snapshot)
    return snapshot


def job_status():
    enabled,_=config()
    if not enabled:
        return {"status":"DISABLED","jobs":[]}
    current=now()
    result=research_jobs.status(_connect,research_jobs.definitions(SECTIONS),current.timestamp())
    calendar_job=next(j for j in result["jobs"] if j["job"]=="CALENDAR_CONTEXT")
    result["calendar"]=research_calendar.read(_connect,current) if calendar_job["status"]=="PASS_COMPLETED" else {"status":"CALENDAR_UNAVAILABLE_OR_PENDING","sessions":[]}
    return result


def _execute_job(job):
    """Dispatch existing bounded engines, with explicit evidence/config gates."""
    if job=="DEAL_REPORTS":
        if not automatic_deals.permitted():
            return "DISABLED_OR_NOT_AUTHORIZED"
        return "PASS_COMPLETED" if automatic_deals.refresh(_connect) else "WAITING_EVIDENCE"
    if job=="FUND_COMPANY_EVIDENCE":
        if not fund_portfolios.permitted() or not automatic_company_evidence.permitted():
            return "DISABLED_OR_NOT_AUTHORIZED"
        ids=fund_portfolios.research_identities()
        if not ids:
            return "WAITING_EVIDENCE"
        automatic_company_evidence.refresh({"enabled":True,"sections":[]},_connect,explicit_isins=ids)
        return "PASS_COMPLETED"
    if job=="FUND_PORTFOLIOS":
        if not fund_portfolios.permitted():
            return "DISABLED_OR_NOT_AUTHORIZED"
        fund_portfolios.refresh()
        return "PASS_COMPLETED"
    if job=="FUND_DISCLOSURES":
        if not fund_disclosures.permitted():
            return "DISABLED_OR_NOT_AUTHORIZED"
        fund_disclosures.refresh()
        return "PASS_COMPLETED"
    if job=="CALENDAR_CONTEXT":
        research_calendar.refresh(_connect)
        return "PASS_COMPLETED"
    if job.startswith("SECTION:"):
        section=job.split(":",1)[1]
        if section not in SECTIONS:
            raise ValueError("INVALID_RESEARCH_SECTION")
        try:
            result=market_snapshot(section) if section in ("NSE","BSE") else fund_snapshot(section)
            _save(section,result)
        except Exception:
            _save(section)
            raise
        return "PASS_COMPLETED"
    if job=="PORTFOLIO_REVIEW":
        if not portfolio_thesis.enabled():
            return "DISABLED_OR_NOT_AUTHORIZED"
        portfolio_thesis.refresh()
        return "PASS_COMPLETED"
    if job=="INSTITUTIONAL_FLOWS":
        if not automatic_institutional.permitted():
            return "DISABLED_OR_NOT_AUTHORIZED"
        automatic_institutional.refresh(_connect,calendar_loader=backend_json)
        return "PASS_COMPLETED"
    if job=="COMPANY_EVIDENCE" and not automatic_company_evidence.permitted():
        return "DISABLED_OR_NOT_AUTHORIZED"
    if job=="COMPANY_NEWS" and not automatic_news.permitted():
        return "DISABLED_OR_NOT_AUTHORIZED"
    if job=="AI_REVIEW" and (not automatic_ai_review.enabled() or not automatic_ai_review.providers()):
        return "DISABLED_OR_NOT_AUTHORIZED"
    snapshot=read_snapshot(False)
    if not snapshot["enabled"]:
        return "DISABLED_OR_NOT_AUTHORIZED"
    # Previously published mature watches still need outcome evaluation even
    # when today's discovery failed; new publication uses READY sections only.
    if job=="WATCH_OUTCOMES":
        watch_outcomes.refresh(snapshot,_connect)
        return "PASS_COMPLETED"
    if not any(s["section"] in ("NSE","BSE") and s["status"]=="READY" for s in snapshot["sections"]):
        return "WAITING_EVIDENCE"
    if job=="COMPANY_EVIDENCE":
        automatic_company_evidence.refresh(snapshot,_connect)
    elif job=="COMPANY_NEWS":
        automatic_news.refresh(snapshot,_connect)
    elif job=="STRATEGY_REPLAY":
        automatic_strategy_validation.refresh(snapshot,_connect)
    elif job=="AI_REVIEW":
        automatic_company_evidence.attach(snapshot,_connect)
        automatic_strategy_validation.read(_connect,snapshot=snapshot)
        automatic_ai_review.refresh(snapshot,_connect)
    else:
        raise ValueError("UNKNOWN_RESEARCH_JOB")
    return "PASS_COMPLETED"


def run_one_job(interval):
    """Claim one due job, run it outside the transaction, persist its result."""
    claimed=research_jobs.claim(_connect,research_jobs.definitions(SECTIONS),now().timestamp())
    if claimed is None:
        return False
    job,token=claimed
    try:
        outcome=_execute_job(job)
    except Exception:
        outcome="FAILED"
    research_jobs.finish(_connect,job,token,now().timestamp(),(research_calendar.POLL_SECONDS if job=="CALENDAR_CONTEXT" else fund_disclosures.INTERVAL if job in ("FUND_DISCLOSURES","FUND_PORTFOLIOS") and outcome!="DISABLED_OR_NOT_AUTHORIZED" else interval),outcome)
    return True


class ResearchScheduler:
    def __init__(self):
        self.task=None
        self.stopping=None

    async def start(self):
        enabled,interval=config()
        if enabled and self.task is None:
            self.stopping=asyncio.Event()
            self.task=asyncio.create_task(self._loop(interval))

    async def _loop(self,interval):
        while not self.stopping.is_set():
            try:
                worked=await asyncio.to_thread(run_one_job,interval)
            except Exception:
                # Storage outage: retry with bounded idle polling rather than spin.
                worked=False
            if not worked:
                try:
                    await asyncio.wait_for(self.stopping.wait(),timeout=research_jobs.POLL_SECONDS)
                except asyncio.TimeoutError:
                    pass

    async def stop(self):
        if self.task is not None:
            self.stopping.set()
            # Do not cancel a worker thread mid-write. Stop after the current
            # bounded job, not after the entire former serial research pass.
            await self.task
            self.task=None


scheduler=ResearchScheduler()
