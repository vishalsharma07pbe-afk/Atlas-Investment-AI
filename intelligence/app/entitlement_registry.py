"""Fail-closed source entitlement manifest and ingestion authorization preflight.

User-supplied declarations are evidence to review, NOT proof of a live connection.
This module never fetches market data or activates any provider.
"""
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import re

PATH = Path(os.getenv("ATLAS_ENTITLEMENT_MANIFEST", "/app/entitlements/sources.json"))
MAX_BYTES = 64_000
SOURCE_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,39}$")
ALLOWED_DATASETS = {"EQUITY_QUOTES", "EQUITY_DAILY", "MF_NAV", "INSTITUTIONAL_FLOWS", "GLOBAL_NEWS"}
ALLOWED_MODES = {"MANUAL_IMPORT", "AUTOMATED_FETCH", "STREAM"}
ALLOWED_PURPOSES = {"PERSONAL_RESEARCH", "REDISTRIBUTION"}
REQUIRED = {"source_id", "dataset", "mode", "purpose", "permission_reference",
            "valid_until", "reviewed_at"}

def _date(value):
    if not isinstance(value, str):
        raise ValueError("INVALID_DATE")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("INVALID_DATE") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("DATE_REQUIRES_TIMEZONE")
    return result.astimezone(timezone.utc)

def validate_manifest(raw):
    if not isinstance(raw, dict) or set(raw) != {"version", "sources"} or raw["version"] != 1:
        raise ValueError("INVALID_MANIFEST_VERSION")
    sources = raw["sources"]
    if not isinstance(sources, list) or len(sources) > 100:
        raise ValueError("INVALID_SOURCE_COUNT")
    seen = set()
    normalized = []
    for entry in sources:
        if not isinstance(entry, dict) or set(entry) != REQUIRED:
            raise ValueError("INVALID_SOURCE_FIELDS")
        sid = entry["source_id"]
        if not isinstance(sid, str) or not SOURCE_RE.fullmatch(sid) or sid in seen:
            raise ValueError("INVALID_OR_DUPLICATE_SOURCE_ID")
        seen.add(sid)
        if (entry["dataset"] not in ALLOWED_DATASETS or
            entry["mode"] not in ALLOWED_MODES or entry["purpose"] not in ALLOWED_PURPOSES):
            raise ValueError("INVALID_SCOPE")
        reference = entry["permission_reference"]
        if not isinstance(reference, str) or not 8 <= len(reference) <= 200:
            raise ValueError("INVALID_PERMISSION_REFERENCE")
        # Do not return the reference: it may include confidential contractual details.
        reviewed = _date(entry["reviewed_at"])
        expires = _date(entry["valid_until"])
        if reviewed > datetime.now(timezone.utc):
            raise ValueError("FUTURE_REVIEW_DATE")
        normalized.append({"source_id": sid, "dataset": entry["dataset"],
                           "mode": entry["mode"], "purpose": entry["purpose"],
                           "valid_until": expires.isoformat(),
                           "reviewed_at": reviewed.isoformat()})
    return normalized

def load_manifest(path=None):
    target = Path(path) if path is not None else PATH
    if not target.is_file():
        return [], "MANIFEST_NOT_CONFIGURED"
    if target.stat().st_size > MAX_BYTES:
        return [], "MANIFEST_TOO_LARGE"
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
        return validate_manifest(raw), None
    except (OSError, UnicodeError, ValueError, TypeError):
        return [], "MANIFEST_INVALID"

def entitlement_preflight(dataset, mode, purpose="PERSONAL_RESEARCH", now=None, path=None):
    if dataset not in ALLOWED_DATASETS or mode not in ALLOWED_MODES or purpose not in ALLOWED_PURPOSES:
        raise ValueError("INVALID_REQUESTED_SCOPE")
    now = now or datetime.now(timezone.utc)
    entries, error = load_manifest(path)
    matches = [e for e in entries if (e["dataset"], e["mode"], e["purpose"]) == (dataset, mode, purpose)]
    valid = [e for e in matches if _date(e["valid_until"]) > now]
    return {"dataset": dataset, "mode": mode, "purpose": purpose,
            "status": "DECLARATION_PRESENT_REQUIRES_INDEPENDENT_VERIFICATION" if valid else "BLOCKED",
            "automatic_collection_enabled": False, "live_market_data_connected": False,
            "independently_verified": False,
            "blockers": ([error] if error else []) + (
                ["NO_MATCHING_ENTITLEMENT_DECLARATION"] if not matches else
                ["ENTITLEMENT_EXPIRED"] if not valid else
                ["INDEPENDENT_ENTITLEMENT_VERIFICATION_REQUIRED", "PROVIDER_AUTHENTICATION_NOT_VERIFIED",
                 "ADAPTER_NOT_ACTIVATED"]),
            "matching_declarations": len(matches),
            "unexpired_declarations": len(valid),
            "notice": "A local declaration is not authorization or proof of provider connectivity."}

def entitlement_summary(path=None):
    entries, error = load_manifest(path)
    now = datetime.now(timezone.utc)
    return {"status": "BLOCKED" if error else "REVIEW_REQUIRED",
            "manifest_error": error,
            "sources": [{**entry, "expired": _date(entry["valid_until"]) <= now,
                         "independently_verified": False, "automatic_collection_enabled": False}
                        for entry in entries],
            "automatic_collection_enabled": False,
            "live_market_data_connected": False,
            "notice": "Declarations are unverified; no automatic ingestion is authorized."}
