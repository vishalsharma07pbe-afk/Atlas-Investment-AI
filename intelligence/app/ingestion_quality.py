"""Fail-closed pre-ingestion batch quality gate.

Validates user-supplied candidate observations without storing, fetching or
publishing them. Entitlement declarations never authorize collection.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator
from .entitlement_registry import entitlement_preflight

MAX_BATCH = 250
MAX_AGE_SECONDS = {"EQUITY_QUOTES": 120, "EQUITY_DAILY": 172800, "MF_NAV": 604800}
MAX_FUTURE_SECONDS = 30

class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instrument: str = Field(min_length=2, max_length=80, pattern=r"^[A-Za-z0-9._:|-]+$")
    observed_at: datetime
    value: Decimal = Field(gt=0, le=Decimal("1000000000"))
    source_id: str = Field(min_length=2, max_length=40, pattern=r"^[A-Z][A-Z0-9_]+$")
    @field_validator("observed_at")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("TIMEZONE_REQUIRED")
        return value
    @field_validator("value")
    @classmethod
    def finite(cls, value):
        if not value.is_finite():
            raise ValueError("NON_FINITE_VALUE")
        return value

class BatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset: Literal["EQUITY_QUOTES", "EQUITY_DAILY", "MF_NAV"]
    mode: Literal["MANUAL_IMPORT", "AUTOMATED_FETCH", "STREAM"]
    candidates: list[Candidate] = Field(min_length=1, max_length=MAX_BATCH)

def inspect_batch(request: BatchRequest, now: datetime | None = None, manifest_path=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("TIMEZONE_REQUIRED")
    now = now.astimezone(timezone.utc)
    entitlement = entitlement_preflight(request.dataset, request.mode,
                                       now=now, path=manifest_path)
    seen = set()
    problems = []
    max_age = MAX_AGE_SECONDS[request.dataset]
    for index, candidate in enumerate(request.candidates):
        timestamp = candidate.observed_at.astimezone(timezone.utc)
        age = (now - timestamp).total_seconds()
        key = (candidate.source_id, candidate.instrument, timestamp)
        reasons = []
        if key in seen:
            reasons.append("DUPLICATE_OBSERVATION")
        seen.add(key)
        if age < -MAX_FUTURE_SECONDS:
            reasons.append("FUTURE_OBSERVATION")
        elif age > max_age:
            reasons.append("STALE_OBSERVATION")
        if reasons:
            problems.append({"index": index, "instrument": candidate.instrument,
                             "reasons": reasons})
    # No declarations are independently verified in ATLAS; never greenlight ingestion.
    return {"status": "REJECTED" if problems else "VALIDATED_NOT_AUTHORIZED",
            "dataset": request.dataset, "mode": request.mode,
            "candidate_count": len(request.candidates),
            "quality_passed": not problems,
            "freshness_sla_seconds": max_age,
            "problems": problems,
            "entitlement_status": entitlement["status"],
            "authorization_blockers": entitlement["blockers"],
            "authorized_to_ingest": False,
            "stored_records": 0,
            "live_market_data_connected": False,
            "notice": "Quality checks are not source authorization. No data was stored, fetched or published."}
