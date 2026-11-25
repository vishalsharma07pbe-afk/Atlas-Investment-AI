"""Fail-closed operational readiness for local research datasets.

This is not a live feed monitor. Source presence, freshness and permission are
independent dimensions; local imports never imply licensed automated access.
"""
from datetime import date, datetime, timezone
from pathlib import Path
import sqlite3
from . import nav_catalog, flow_ledger, news_ledger, quote_recovery
from .config import settings
from .market_client import backend_json
from zoneinfo import ZoneInfo
from . import nav_auto_refresh

SOURCES = (
    ("MUTUAL_FUND_NAV", "Mutual fund NAV", "nav_schemes", "nav_date", "scheme_code", 5, "date"),
    ("INSTITUTIONAL_FLOWS", "Institutional flow evidence", "flow_evidence", "trade_date", "trade_date", 3, "date"),
    ("GLOBAL_NEWS", "Global news evidence", "news_events", "published_at", "published_at", 72, "hours"),
)
SOURCE_PATHS = {
    "MUTUAL_FUND_NAV": lambda: nav_catalog.DB_PATH,
    "INSTITUTIONAL_FLOWS": lambda: flow_ledger.DB_PATH,
    "GLOBAL_NEWS": lambda: news_ledger.DB_PATH,
}

def _snapshot(path: Path, table: str, time_column: str):
    # Read-only mode avoids creating missing databases and bypasses schema mutation.
    if not path.is_file():
        return 0, None, "NOT_IMPORTED"
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2) as db:
            # All table/column identifiers are hardcoded in SOURCES, not user input.
            count, latest = db.execute(
                f"SELECT COUNT(*), MAX({time_column}) FROM {table}"
            ).fetchone()
            return count, latest, None if count else "NOT_IMPORTED"
    except (sqlite3.Error, OSError, ValueError):
        return 0, None, "STORAGE_UNAVAILABLE"

def _age(latest: str, unit: str, now: datetime):
    if unit == "date":
        return (now.date() - date.fromisoformat(latest)).days
    stamp = datetime.fromisoformat(latest)
    if stamp.tzinfo is None:
        raise ValueError("timestamp without timezone")
    return (now - stamp.astimezone(timezone.utc)).total_seconds() / 3600

def live_feed_observation(now: datetime):
    """Require permission, transport and at least one fresh subscribed tick.
    Never expose instrument selections or credentials in this public summary.
    """
    from .upstox_quote_worker import quote_worker
    if not (settings.provider == "UPSTOX" and settings.licensed_data_access and settings.entitlement_confirmed):
        return False
    if not quote_worker.running or not quote_worker.cache.connected:
        return False
    return any(quote_worker.cache.snapshot(key, int(now.timestamp()*1000))["status"] == "LIVE"
               for key in tuple(quote_worker.active_keys))


def backend_evidence(health, now):
    rows = []
    ist_today = now.astimezone(ZoneInfo("Asia/Kolkata")).date()
    for key, code, label, unit, threshold in (
        ("upstoxRegistry", "UPSTOX_REGISTRY", "Upstox instrument registry", "hours", 36),
        ("upstoxDailyHistory", "UPSTOX_DAILY_HISTORY", "Upstox validated daily history", "date", 4),
        ("officialAmfiNav", "OFFICIAL_AMFI_NAV", "Official AMFI NAV", "date", 5),
    ):
        item = health.get(key) if isinstance(health, dict) else None
        count = item.get("records") if isinstance(item, dict) else None
        latest = item.get("latest") if isinstance(item, dict) else None
        status = "STORAGE_UNAVAILABLE"
        age = None
        if type(count) is int and count >= 0:
            if count == 0:
                status = "NOT_IMPORTED"
            else:
                try:
                    age = (ist_today - date.fromisoformat(latest)).days if unit == "date" else _age(latest, unit, now)
                    status = "FUTURE_TIMESTAMP" if age < 0 else "STALE_DATA" if age > threshold else "RECENT_LOCAL_EVIDENCE"
                except (ValueError, TypeError, OverflowError):
                    status = "INVALID_TIMESTAMP"
        rows.append({"code":code,"label":label,"records":count if type(count) is int and count>=0 else None,
                     "latest_observed_at":latest if isinstance(latest,str) else None,"age":round(age,2) if age is not None else None,
                     "age_unit":unit,"status":status,"freshness_threshold":threshold,
                     "ingestion_mode":"STORED_PROVIDER_EVIDENCE","independently_verified":False,
                     "automatic_collection_enabled":bool(isinstance(health,dict) and health.get("scheduledFeedsEnabled") is True and code!="UPSTOX_DAILY_HISTORY"),
                     "usable_as_live_market_data":False})
    return rows


def readiness(now: datetime | None = None, health_loader=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(timezone.utc)
    datasets = []
    for code, label, table, column, _, max_age, unit in SOURCES:
        count, latest, issue = _snapshot(SOURCE_PATHS[code](), table, column)
        age = None
        if issue is None:
            try:
                age = _age(latest, unit, now)
                if age < 0:
                    issue = "FUTURE_TIMESTAMP"
                elif age > max_age:
                    issue = "STALE_DATA"
            except (ValueError, TypeError, OverflowError):
                issue = "INVALID_TIMESTAMP"
        datasets.append({
            "code": code, "label": label, "records": count,
            "latest_observed_at": latest, "age": round(age, 2) if age is not None else None,
            "age_unit": unit, "freshness_threshold": max_age,
            "status": issue or "RECENT_LOCAL_EVIDENCE",
            "ingestion_mode": "LOCAL_CATALOG" if code == "MUTUAL_FUND_NAV" else "MANUAL_IMPORT",
            "independently_verified": False,
            "automatic_collection_enabled": code == "MUTUAL_FUND_NAV" and nav_auto_refresh.config()["enabled"],
            "usable_as_live_market_data": False,
        })
    from .autonomous_research import config as research_config, read_snapshot, job_status
    automatic, interval = research_config()
    try:
        health = (health_loader or backend_json)("/api/v1/data-health/summary")
    except Exception:
        health = None
    provider_rows = backend_evidence(health, now)
    live = live_feed_observation(now)
    blockers = []
    if not live:
        blockers.append("VERIFIED_LIVE_FEED_UNAVAILABLE")
    if not settings.licensed_data_access:
        blockers.append("MARKET_DATA_USAGE_RIGHTS_NOT_CONFIRMED")
    if not settings.entitlement_confirmed:
        blockers.append("MARKET_DATA_ENTITLEMENT_NOT_CONFIRMED")
    if not isinstance(health, dict):
        blockers.append("BACKEND_EVIDENCE_UNAVAILABLE")
    research_sections = []
    research_jobs = {"status":"DISABLED","jobs":[]}
    if automatic:
        try:
            snapshot = read_snapshot(include_ai=False)
            research_sections = [{"section":row["section"],"status":row["status"],"generated_at":row["generated_at"]}
                                 for row in snapshot["sections"]]
        except (OSError, ValueError, sqlite3.Error):
            blockers.append("RESEARCH_SNAPSHOT_UNAVAILABLE")
    if automatic:
        try:
            research_jobs=job_status()
        except (OSError, ValueError, sqlite3.Error):
            research_jobs={"status":"UNAVAILABLE","jobs":[]}
            blockers.append("RESEARCH_JOB_LEDGER_UNAVAILABLE")
    return {
        "generated_at": now.isoformat(),
        "status": "AUTOMATIC_RESEARCH_CONFIGURED" if automatic else "AUTOMATIC_RESEARCH_DISABLED",
        "live_market_data_connected": live,
        "automatic_research_enabled": automatic,
        "actionable_recommendations_enabled": False,
        "provider_mode": settings.provider,
        "research_interval_seconds": interval,
        "research_sections": research_sections,
        "research_jobs": research_jobs,
        "provider_http_recovery": quote_recovery.status(now.timestamp()),
        "blockers": blockers,
        "datasets": datasets,
        "backend_evidence": provider_rows,
        "notice": "Scheduler configuration, stored evidence and fresh live ticks are separate. Recent evidence is not proof of a qualified investment recommendation.",
    }
