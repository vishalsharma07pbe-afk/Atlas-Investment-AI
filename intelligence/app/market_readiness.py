"""Fail-closed market data readiness evaluation of recorded backend health."""
from datetime import date, datetime, timezone
from typing import Any
from pydantic import BaseModel, Field

class ReadinessPolicy(BaseModel):
    max_calendar_age_days: int = Field(default=7, ge=0, le=30)
    minimum_instruments: int = Field(default=1, ge=1, le=1000000)
    minimum_candles: int = Field(default=1, ge=1, le=100000000)
    require_live_feed: bool = True

def evaluate_readiness(health: dict[str, Any], policy: ReadinessPolicy, today: date | None = None) -> dict:
    """Unknown/malformed evidence is a blocker, never a passing signal."""
    if not isinstance(health, dict):
        raise ValueError("Invalid health payload")
    today = today or datetime.now(timezone.utc).date()
    blockers: list[str] = []
    instruments = health.get("instrumentCount")
    candles = health.get("candleCount")
    issues = health.get("unresolvedIssueCount")
    if type(instruments) is not int or instruments < policy.minimum_instruments:
        blockers.append("INSUFFICIENT_INSTRUMENT_COVERAGE")
    if type(candles) is not int or candles < policy.minimum_candles:
        blockers.append("INSUFFICIENT_CANDLE_COVERAGE")
    if type(issues) is not int or issues < 0 or issues > 0:
        blockers.append("UNRESOLVED_OR_UNKNOWN_QUALITY_EVENTS")
    if policy.require_live_feed and health.get("liveMarketDataConnected") is not True:
        blockers.append("VERIFIED_LIVE_FEED_UNAVAILABLE")
    sources = health.get("sources")
    if not isinstance(sources, list) or not sources:
        blockers.append("NO_SOURCE_PROVENANCE")
        sources = []
    dated = []
    for source in sources:
        if not isinstance(source, dict):
            blockers.append("INVALID_SOURCE_PROVENANCE")
            continue
        raw = source.get("latest_candle")
        if raw:
            try:
                parsed = date.fromisoformat(str(raw)[:10])
                if parsed > today:
                    blockers.append("FUTURE_DATED_SOURCE")
                else:
                    dated.append(parsed)
            except ValueError:
                blockers.append("INVALID_SOURCE_DATE")
    latest = max(dated) if dated else None
    age = (today - latest).days if latest else None
    if age is None:
        blockers.append("NO_DATED_SOURCE_EVIDENCE")
    elif age > policy.max_calendar_age_days:
        blockers.append("STALE_MARKET_DATA")
    blockers = sorted(set(blockers))
    return {
        "status": "READY" if not blockers else "BLOCKED",
        "research_signals_enabled": not blockers,
        "blockers": blockers,
        "latest_source_date": latest.isoformat() if latest else None,
        "source_age_calendar_days": age,
        "instrument_count": instruments if type(instruments) is int else None,
        "candle_count": candles if type(candles) is int else None,
        "unresolved_quality_events": issues if type(issues) is int else None,
        "policy": policy.model_dump(),
        "notice": "Read-only evaluation of recorded backend health. READY is not a guarantee of market accuracy, feed entitlement or trading suitability.",
    }
