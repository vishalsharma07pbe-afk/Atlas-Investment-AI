"""Fail-closed operational readiness for local research datasets.

This is not a live feed monitor. Source presence, freshness and permission are
independent dimensions; local imports never imply licensed automated access.
"""
from datetime import date, datetime, timezone
from pathlib import Path
import sqlite3
from . import nav_catalog, flow_ledger, news_ledger
from .config import settings

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

def readiness(now: datetime | None = None):
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
            "ingestion_mode": "MANUAL_IMPORT",
            "independently_verified": False,
            "automatic_collection_enabled": False,
            "usable_as_live_market_data": False,
        })
    provider_configured = settings.provider != "MANUAL_CSV"
    blockers = ["NO_VERIFIED_LIVE_PROVIDER_ADAPTER", "AUTOMATED_SOURCE_RIGHTS_NOT_VERIFIED"]
    if not settings.licensed_data_access:
        blockers.append("MARKET_DATA_USAGE_RIGHTS_NOT_CONFIRMED")
    if not settings.entitlement_confirmed:
        blockers.append("MARKET_DATA_ENTITLEMENT_NOT_CONFIRMED")
    if not provider_configured:
        blockers.append("MARKET_PROVIDER_MANUAL_ONLY")
    return {
        "generated_at": now.isoformat(),
        "status": "BLOCKED_FOR_AUTOMATED_MARKET_RESEARCH",
        "live_market_data_connected": False,
        "automatic_research_enabled": False,
        "actionable_recommendations_enabled": False,
        "provider_mode": settings.provider,
        "blockers": blockers,
        "datasets": datasets,
        "notice": "Recent manually supplied evidence is not an authenticated live market feed. No automated trading or recommendations.",
    }
