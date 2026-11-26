"""Authorized, read-only P1 research adapters with explicit provenance.

This module normalizes provider evidence; it never emits a buy/sell verdict or
silently substitutes a missing field.  A section can fail independently while
the rest of a company report remains usable.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from math import isfinite
import re
from urllib.parse import urlencode, quote

from .multi_provider_quotes import KEY_RE, ProviderFailure, _request, _timestamp

BASE_URL = "https://api.upstox.com"
ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
ALLOWED_INTERVALS = {"1D", "1M"}


def _token() -> str:
    value = os.getenv("UPSTOX_ACCESS_TOKEN", "").strip()
    if not value:
        raise ProviderFailure("UPSTOX_TOKEN_MISSING")
    return value


def _get(path: str, params: dict[str, str] | None = None):
    url = BASE_URL + path
    if params:
        url += "?" + urlencode(params)
    body = _request(url, {
        "Authorization": "Bearer " + _token(),
        "Accept": "application/json",
    })
    if body.get("status") != "success" or "data" not in body:
        raise ProviderFailure("UPSTOX_SCHEMA_MISMATCH")
    return body["data"]


def _source(endpoint: str) -> dict:
    return {
        "provider": "UPSTOX",
        "endpoint": endpoint,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "access": "AUTHORIZED_READ_ONLY_API",
    }


def _safe_section(name: str, endpoint: str, loader) -> dict:
    try:
        data = loader()
        if not data:
            raise ProviderFailure("NO_PROVIDER_RECORDS")
        return {"name": name, "status": "AVAILABLE", "data": data,
                "source": _source(endpoint), "error": None}
    except ProviderFailure as exc:
        return {"name": name, "status": "UNAVAILABLE", "data": None,
                "source": _source(endpoint), "error": str(exc)}


def _ratio_number(value):
    if value is None:
        return None
    try:
        number = float(str(value).strip().rstrip("%"))
        return number if isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _normalize_ratios(rows) -> list[dict]:
    if not isinstance(rows, list):
        raise ProviderFailure("UPSTOX_RATIO_SCHEMA_INVALID")
    result = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("name"), str):
            continue
        company = _ratio_number(row.get("company_value"))
        sector = _ratio_number(row.get("sector_value"))
        result.append({
            "name": row["name"],
            "company_value": company,
            "sector_value": sector,
            "unit": "PERCENT" if "%" in str(row.get("company_value", "")) else "RATIO",
            "sector_unit": "PERCENT" if "%" in str(row.get("sector_value", "")) else "RATIO",
            "relative_difference_percent": (
                round((company - sector) / abs(sector) * 100, 2)
                if company is not None and sector not in (None, 0)
                and ("%" in str(row.get("company_value", ""))) == ("%" in str(row.get("sector_value", ""))) else None
            ),
        })
    return result


def company_research(isin: str, instrument_key: str | None = None) -> dict:
    isin = isin.strip().upper()
    if not ISIN_RE.fullmatch(isin):
        raise ValueError("INVALID_ISIN")
    if instrument_key is not None and not KEY_RE.fullmatch(instrument_key):
        raise ValueError("INVALID_INSTRUMENT_KEY")

    encoded_isin = quote(isin, safe="")
    sections = {
        "profile": _safe_section("profile", f"/v2/fundamentals/{encoded_isin}/profile",
            lambda: _get(f"/v2/fundamentals/{encoded_isin}/profile")),
        "ratios": _safe_section("ratios", f"/v2/fundamentals/{encoded_isin}/key-ratios",
            lambda: _normalize_ratios(_get(f"/v2/fundamentals/{encoded_isin}/key-ratios"))),
        "income_statement": _safe_section("income_statement", f"/v2/fundamentals/{encoded_isin}/income-statement",
            lambda: _get(f"/v2/fundamentals/{encoded_isin}/income-statement",
                         {"type": "consolidated", "time_period": "yearly", "fs": "true"})),
        "balance_sheet": _safe_section("balance_sheet", f"/v2/fundamentals/{encoded_isin}/balance-sheet",
            lambda: _get(f"/v2/fundamentals/{encoded_isin}/balance-sheet",
                         {"type": "consolidated", "time_period": "yearly", "fs": "true"})),
        "cash_flow": _safe_section("cash_flow", f"/v2/fundamentals/{encoded_isin}/cash-flow",
            lambda: _get(f"/v2/fundamentals/{encoded_isin}/cash-flow",
                         {"type": "consolidated", "time_period": "yearly", "fs": "true"})),
        "shareholding": _safe_section("shareholding", f"/v2/fundamentals/{encoded_isin}/share-holdings",
            lambda: _get(f"/v2/fundamentals/{encoded_isin}/share-holdings")),
        "corporate_actions": _safe_section("corporate_actions", f"/v2/fundamentals/{encoded_isin}/corporate-actions",
            lambda: _get(f"/v2/fundamentals/{encoded_isin}/corporate-actions")),
    }
    # The documented competitor endpoint is ISIN based. Retain the optional
    # instrument_key argument and response field for existing API callers.
    sections["competitors"] = _safe_section(
        "competitors", f"/v2/fundamentals/{encoded_isin}/competitors",
        lambda: _get(f"/v2/fundamentals/{encoded_isin}/competitors"))
    available = sum(1 for value in sections.values() if value["status"] == "AVAILABLE")
    return {
        "isin": isin,
        "instrument_key": instrument_key,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "coverage": {"available_sections": available, "total_sections": len(sections)},
        "sections": sections,
        "interpretation": {
            "valuation": "Company ratios are compared with the provider's current sector values; this is not a fair-value estimate.",
            "statements": "Consolidated yearly summaries; verify period labels and filings before decisions.",
            "corporate_actions": "Events are shown as reported and are not automatically treated as price adjustments.",
        },
        "recommendation": None,
        "notice": "Evidence dashboard only. Missing fields remain missing; no investment recommendation is generated.",
    }


def company_news(instrument_keys: list[str], page_size: int = 20) -> dict:
    keys = list(dict.fromkeys(key.strip() for key in instrument_keys if key.strip()))
    if not keys or len(keys) > 30 or any(not KEY_RE.fullmatch(key) for key in keys):
        raise ValueError("INVALID_INSTRUMENT_KEYS")
    page_size = max(1, min(int(page_size), 100))
    data = _get("/v2/news", {
        "category": "instrument_keys", "instrument_keys": ",".join(keys),
        "page_number": "1", "page_size": str(page_size),
    })
    if not isinstance(data, dict):
        raise ProviderFailure("UPSTOX_NEWS_SCHEMA_INVALID")
    seen: set[tuple[str, str, str]] = set()
    returned_keys = []
    articles = []
    for instrument_key, rows in data.items():
        if instrument_key not in keys or not isinstance(rows, list):
            continue
        returned_keys.append(instrument_key)
        for row in rows:
            if not isinstance(row, dict):
                continue
            link = row.get("article_link")
            stamp = row.get("published_time")
            if not isinstance(link, str) or not link.startswith("https://"):
                continue
            try:
                published = _timestamp(stamp).isoformat()
            except ProviderFailure:
                continue
            dedupe = (instrument_key, link, published)
            if dedupe in seen:
                continue
            seen.add(dedupe)
            articles.append({
                "instrument_key": instrument_key,
                "headline": str(row.get("heading") or "Untitled article")[:500],
                "summary": str(row.get("summary") or "")[:2000],
                "url": link,
                "thumbnail": row.get("thumbnail"),
                "published_at": published,
                "sentiment": "NOT_ANALYZED",
                "source_provider": "UPSTOX_NEWS",
            })
    articles.sort(key=lambda item: item["published_at"], reverse=True)
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "articles": articles,
            "count": len(articles), "returned_keys": returned_keys, "source": _source("/v2/news"),
            "notice": "Provider headlines and summaries with citations. Sentiment is not inferred."}


def institutional_activity(interval: str = "1D") -> dict:
    interval = interval.upper()
    if interval not in ALLOWED_INTERVALS:
        raise ValueError("INVALID_INTERVAL")
    params = {"interval": interval, "data_type": "NSE_EQ|CASH"}
    participants = {}
    for participant in ("fii", "dii"):
        endpoint = f"/v2/market/{participant}"
        section = _safe_section(participant.upper(), endpoint,
                                lambda p=endpoint: _get(p, params))
        if section["status"] == "AVAILABLE":
            raw = section["data"]
            rows = raw.get("NSE_EQ|CASH", []) if isinstance(raw, dict) else []
            normalized = []
            for row in rows if isinstance(rows, list) else []:
                if not isinstance(row, dict):
                    continue
                try:
                    observed = _timestamp(row.get("time_stamp")).isoformat()
                except ProviderFailure:
                    continue
                buy = _ratio_number(row.get("buy_amount"))
                sell = _ratio_number(row.get("sell_amount"))
                normalized.append({**row, "observed_at": observed,
                                   "net_amount": round(buy - sell, 2) if buy is not None and sell is not None else None})
            section["data"] = normalized
        participants[participant] = section
    return {"interval": interval, "market": "NSE_CASH", "unit": "PROVIDER_REPORTED",
            "generated_at": datetime.now(timezone.utc).isoformat(), "participants": participants,
            "notice": "Official aggregate institutional activity; not evidence of activity in an individual stock."}
