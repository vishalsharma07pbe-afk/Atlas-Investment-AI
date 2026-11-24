"""Bounded public-evidence AI reviews; independent of browser and holdings.

Existing provider permissions and shared budget reservations remain authoritative.
No private portfolio inputs, arbitrary text, targets, or trade actions enter this path.
"""
from __future__ import annotations

from contextlib import closing
from datetime import date, datetime, timezone, timedelta
from hashlib import sha256
import json
import math
import os
import re
import sqlite3

from . import ai_failover

VERSION = "AUTO-GROUNDED-1"
HORIZONS = ("SWING", "SHORT_TERM", "LONG_TERM")
SYMBOL = re.compile(r"^[A-Z0-9._&-]{1,40}$")
UNSAFE = re.compile(r"\b(?:buy|sell|stop.loss|price target|guaranteed|guarantee|risk.free)\b", re.I)


def enabled():
    return os.getenv("ATLAS_AUTOMATIC_AI_REVIEW_ENABLED", "false").lower() == "true"


def providers():
    if not enabled():
        return []
    external = os.getenv("ATLAS_AUTOMATIC_EXTERNAL_AI_ALLOWED", "false").lower() == "true"
    order = ai_failover._order()
    # Local-first even if the manual router has a different preference.
    ordered = sorted(order, key=lambda p: p != "OLLAMA")
    return [p for p in ordered if (p == "OLLAMA" or external) and ai_failover._enabled(p)][:2]


def evidence(candidate, horizon):
    if horizon not in HORIZONS or candidate.get("exchange") not in ("NSE", "BSE"):
        raise ValueError("INVALID_CANDIDATE")
    symbol = candidate.get("symbol")
    if not isinstance(symbol, str) or not SYMBOL.fullmatch(symbol):
        raise ValueError("INVALID_SYMBOL")
    observed = date.fromisoformat(candidate["as_of"]).isoformat()
    numeric = {}
    for key in ("close", "history_count", "atr_percent", "momentum_20d_percent",
                "relative_volume_20", "rsi_14", "median_daily_traded_value"):
        value = candidate.get(key)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("INVALID_OBSERVATION")
        numeric[key] = value
    if not {"close", "history_count", "atr_percent"} <= numeric.keys():
        raise ValueError("INCOMPLETE_OBSERVATIONS")
    adjustment = candidate.get("adjustment_status")
    if adjustment not in ("RAW_UNADJUSTED", "ADJUSTED"):
        raise ValueError("INVALID_ADJUSTMENT")
    return {"version": VERSION, "symbol": symbol, "exchange": candidate["exchange"],
            "as_of": observed, "horizon": horizon, "adjustment": adjustment,
            "observations": numeric,
            "missing": ["Live liquidity", "Current company fundamentals", "Valuation",
                        "Institutional flows", "Material news", "Strategy validation"]}


def identity(pack):
    return sha256(json.dumps(pack, sort_keys=True, allow_nan=False).encode()).hexdigest()


def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS automatic_ai_reviews(
        evidence_hash TEXT PRIMARY KEY, attempted_at TEXT NOT NULL,
        status TEXT NOT NULL, result TEXT NOT NULL)""")


def _read(connect, key):
    with closing(connect()) as db:
        _table(db)
        row = db.execute("SELECT attempted_at,status,result FROM automatic_ai_reviews WHERE evidence_hash=?", (key,)).fetchone()
        return (row[0], row[1], json.loads(row[2])) if row else None


def _claim(connect, key, now):
    with closing(connect()) as db, db:
        _table(db)
        cursor = db.execute("""INSERT INTO automatic_ai_reviews VALUES(?,?,'RUNNING','{}')
            ON CONFLICT(evidence_hash) DO UPDATE SET attempted_at=excluded.attempted_at,
            status='RUNNING',result='{}'
            WHERE automatic_ai_reviews.status!='COMPLETE'
              AND automatic_ai_reviews.attempted_at<=?""",
            (key, now.isoformat(), (now-timedelta(hours=6)).isoformat()))
        return cursor.rowcount == 1


def _finish(connect, key, status, result):
    with closing(connect()) as db, db:
        db.execute("UPDATE automatic_ai_reviews SET status=?,result=? WHERE evidence_hash=?",
                   (status, json.dumps(result, allow_nan=False), key))
        db.execute("DELETE FROM automatic_ai_reviews WHERE attempted_at<?",
                   ((datetime.now(timezone.utc)-timedelta(days=14)).isoformat(),))


def _review(pack, provider, runner):
    # Text is entirely constructed from public, typed observations.
    prompt = ("Review this dated technical watch for research purposes only. "
              "Use only the supplied evidence. Give cautious descriptive findings, "
              "not trade actions, targets, predictions or confidence percentages. "
              "Cite OBS for numeric observations or LIMITS for missing evidence. "
              "Do not invent facts. Return the required JSON.\n"
              + json.dumps({"OBS": {k:v for k,v in pack.items() if k!="missing"},
                            "LIMITS": pack["missing"]}, ensure_ascii=True))
    result = runner(prompt, ["OBS", "LIMITS"], providers=[provider])
    response = result.get("response")
    if result.get("status") != "MODEL_GROUNDED" or result.get("provider") != provider or not isinstance(response, dict):
        return None
    findings = response.get("findings")
    if not isinstance(findings, list) or not 1<=len(findings)<=8:
        return None
    clean = []
    for finding in findings:
        if not isinstance(finding, dict):
            return None
        statement, citations = finding.get("statement"), finding.get("evidence_ids")
        if (not isinstance(statement, str) or not 1<=len(statement)<=500
                or ai_failover.BLOCKED.search(statement) or UNSAFE.search(statement)
                or not isinstance(citations, list) or not 1<=len(citations)<=5
                or any(c not in ("OBS", "LIMITS") for c in citations)):
            return None
        clean.append({"statement": statement, "evidence_ids": citations})
    # Never persist raw prompts, raw answers, actions, confidence, or provider errors.
    return {"provider": provider, "findings": clean}


def candidates(snapshot):
    for section in snapshot["sections"]:
        if section["section"] not in ("NSE", "BSE") or section["status"]!="READY":
            continue
        for horizon in HORIZONS:
            for item in (section.get("result") or {}).get("horizons", {}).get(horizon, {}).get("candidates", []):
                try:
                    pack = evidence(item, horizon)
                    yield item, pack, identity(pack)
                except (ValueError, KeyError, TypeError, OverflowError):
                    continue


def refresh(snapshot, connect, runner=ai_failover.grounded_research):
    if not snapshot["enabled"] or not enabled():
        return
    selected = providers()
    if not selected:
        return
    now = datetime.now(timezone.utc)
    # One new/expired evidence pack per pass, at most two provider calls.
    # Persist the claim before I/O so failures and restarts cannot spin.
    for _, pack, key in candidates(snapshot):
        if not _claim(connect, key, now):
            continue
        reviews = []
        for provider in selected:
            try:
                review = _review(pack, provider, runner)
                if review is not None:
                    reviews.append(review)
            except Exception:
                # Provider failure must not disrupt deterministic research.
                continue
        result = {"reviews": reviews, "evidence": pack, "reviewed_at": now.isoformat(),
                  "notice": "Unverified model commentary on the same dated evidence; citations are not proof of correctness. No consensus trade verdict."}
        _finish(connect, key, "COMPLETE" if len(reviews)==len(selected) else "PARTIAL" if reviews else "UNAVAILABLE", result)
        return


def attach(snapshot, connect):
    # Only display reviews for the exact current evidence and permitted providers.
    if not snapshot["enabled"] or not enabled():
        snapshot["automatic_ai_status"] = "DISABLED"
        return snapshot
    allowed = providers()
    snapshot["automatic_ai_status"] = "ENABLED" if allowed else "NO_CONFIGURED_PROVIDER"
    for item, _, key in candidates(snapshot):
        row = _read(connect, key)
        if row and row[1] in ("COMPLETE", "PARTIAL"):
            result = row[2]
            reviews = [r for r in result.get("reviews", []) if r["provider"] in allowed]
            if reviews:
                item["ai_review"] = {**result, "reviews": reviews}
    return snapshot
