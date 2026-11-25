"""Read-only authorized quote adapters; never submit orders or silently invent timestamps."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import os
import re
import sqlite3
from urllib.parse import urlsplit
from . import quote_recovery
import httpx
from urllib.parse import quote, urlencode
from .provider_router import Quote, ProviderFailure, ReadOnlyRouter, CircuitBreaker

SYMBOL_RE = re.compile(r"^[A-Z0-9._&-]{1,40}$")
KEY_RE = re.compile(r"^[A-Z0-9_|.-]{3,120}$")
DEFAULT_TIMEOUT = 5
# Circuit state survives separate HTTP requests within this process.
quote_breaker = CircuitBreaker()

def _request(url, headers):
    provider={"api.upstox.com":"UPSTOX","api.polygon.io":"POLYGON"}.get(urlsplit(url).hostname)
    if provider is None:
        raise ProviderFailure("PROVIDER_REQUEST_FAILED")
    try:
        claim=quote_recovery.claim(provider)
    except (OSError,sqlite3.Error):
        raise ProviderFailure("RECOVERY_STORAGE_UNAVAILABLE") from None
    if claim is None:
        raise ProviderFailure("PROVIDER_RECOVERY_COOLDOWN")
    reason="PROVIDER_REQUEST_FAILED"
    retry_after=None
    try:
        safe_headers = {**headers, "User-Agent": "ATLAS-Research/1.0"}
        response = httpx.get(url, headers=safe_headers, timeout=DEFAULT_TIMEOUT,
                             follow_redirects=False)
        if response.status_code in (401, 403):
            raise ProviderFailure("PROVIDER_ACCESS_REJECTED")
        if response.status_code == 429:
            raw=response.headers.get("Retry-After","")
            if isinstance(raw,str) and raw.isascii() and raw.isdigit() and len(raw)<=6:
                retry_after=int(raw)
            raise ProviderFailure("PROVIDER_RATE_LIMITED")
        if response.status_code != 200:
            raise ProviderFailure("PROVIDER_HTTP_FAILURE")
        raw = response.content
        if len(raw) > 262144:
            raise ProviderFailure("PROVIDER_RESPONSE_TOO_LARGE")
        result=json.loads(raw)
        if not isinstance(result,dict):
            raise ProviderFailure("PROVIDER_SCHEMA_INVALID")
        reason=None
        return result
    except httpx.HTTPError:
        raise ProviderFailure("PROVIDER_REQUEST_FAILED") from None
    except ProviderFailure as exc:
        reason=str(exc)
        raise
    except (ValueError, KeyError, TypeError):
        reason="PROVIDER_SCHEMA_INVALID"
        raise ProviderFailure(reason) from None
    finally:
        try:
            quote_recovery.finish(provider,claim,reason,retry_after)
        except (OSError,sqlite3.Error):
            # An unfinished claim remains bounded by its lease; do not expose
            # storage errors, filesystem paths or provider credentials.
            pass

def _timestamp(value):
    if isinstance(value, bool):
        raise ProviderFailure("INVALID_TIMESTAMP")
    if isinstance(value, (int, float)):
        # Provider timestamps must be explicit epoch milliseconds.
        if not 1_000_000_000_000 <= value <= 9_999_999_999_999:
            raise ProviderFailure("INVALID_TIMESTAMP")
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    if isinstance(value, str):
        if value.isdigit():
            numeric = int(value)
            if 1_000_000_000_000 <= numeric <= 9_999_999_999_999:
                return datetime.fromtimestamp(numeric / 1000, tz=timezone.utc)
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is not None and parsed.utcoffset() is not None:
                return parsed.astimezone(timezone.utc)
        except ValueError:
            pass
    raise ProviderFailure("INVALID_TIMESTAMP")

def _price(value):
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ProviderFailure("INVALID_PRICE") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise ProviderFailure("INVALID_PRICE")
    return str(parsed)

def upstox_quote(symbol, instrument_key, token):
    """Upstox V3 full quote; requires an explicit, verified NSE/BSE instrument mapping."""
    if not SYMBOL_RE.fullmatch(symbol) or not KEY_RE.fullmatch(instrument_key) or not token:
        raise ProviderFailure("INVALID_UPSTOX_CONFIGURATION")
    url = "https://api.upstox.com/v3/market-quote/quotes?" + urlencode({"instrument_key": instrument_key})
    body = _request(url, {"Authorization": "Bearer " + token, "Accept": "application/json"})
    data = body.get("data")
    if body.get("status") != "success" or not isinstance(data, dict) or len(data) != 1:
        raise ProviderFailure("UPSTOX_SCHEMA_MISMATCH")
    item = next(iter(data.values()))
    if not isinstance(item, dict) or item.get("instrument_token") != instrument_key:
        raise ProviderFailure("UPSTOX_INSTRUMENT_MISMATCH")
    return Quote(symbol=symbol, price=_price(item.get("last_price")),
                 observed_at=_timestamp(item.get("last_trade_time")), provider="UPSTOX")

def polygon_quote(symbol, api_key):
    """Polygon/Massive last-trade endpoint for supported US symbols only."""
    if not SYMBOL_RE.fullmatch(symbol) or not api_key:
        raise ProviderFailure("INVALID_POLYGON_CONFIGURATION")
    url = "https://api.polygon.io/v2/last/trade/" + quote(symbol, safe="") + "?" + urlencode({"apiKey": api_key})
    body = _request(url, {"Accept": "application/json"})
    result = body.get("results")
    if body.get("status") not in ("OK", "DELAYED") or not isinstance(result, dict):
        raise ProviderFailure("POLYGON_SCHEMA_MISMATCH")
    if result.get("T") != symbol:
        raise ProviderFailure("POLYGON_SYMBOL_MISMATCH")
    # Polygon last-trade timestamp is nanoseconds since epoch, not milliseconds.
    ns = result.get("t")
    if isinstance(ns, bool) or not isinstance(ns, int) or ns < 1_000_000_000_000_000_000:
        raise ProviderFailure("POLYGON_TIMESTAMP_INVALID")
    return Quote(symbol=symbol, price=_price(result.get("p")),
                 observed_at=datetime.fromtimestamp(ns / 1_000_000_000, tz=timezone.utc),
                 provider="POLYGON")

def _mapping():
    """JSON map of exact local symbols to authorized Upstox instrument keys."""
    raw = os.getenv("ATLAS_UPSTOX_SYMBOL_MAP", "{}")
    if len(raw) > 20000:
        return {}
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    if not isinstance(parsed, dict) or len(parsed) > 300:
        return {}
    return {s:k for s,k in parsed.items() if isinstance(s,str) and isinstance(k,str)
            and SYMBOL_RE.fullmatch(s) and KEY_RE.fullmatch(k)}

def configured_router():
    """No implicit entitlement: each provider requires explicit rights and credential gates."""
    mapping = _mapping()
    upstox_token = os.getenv("UPSTOX_ACCESS_TOKEN", "")
    polygon_key = os.getenv("ATLAS_POLYGON_API_KEY", "")
    upstox_allowed = (os.getenv("ATLAS_UPSTOX_QUOTES_AUTHORIZED", "false").lower() == "true"
                      and bool(upstox_token) and bool(mapping))
    polygon_allowed = (os.getenv("ATLAS_POLYGON_QUOTES_AUTHORIZED", "false").lower() == "true"
                       and bool(polygon_key))
    # Never substitute a US ticker quote for an Indian equity with the same symbol.
    us_symbols = set(os.getenv("ATLAS_POLYGON_US_SYMBOLS", "").split(","))
    us_symbols = {s for s in us_symbols if SYMBOL_RE.fullmatch(s)}
    adapters = [
        ("UPSTOX", lambda s: upstox_quote(s, mapping[s], upstox_token),
         upstox_allowed and bool(mapping)),
        ("POLYGON", lambda s: polygon_quote(s, polygon_key), polygon_allowed),
    ]
    # Route eligibility is checked per requested symbol, not merely per provider.
    class SymbolScopedRouter(ReadOnlyRouter):
        def quote(self, symbol, max_age_seconds=60):
            if symbol in mapping and symbol in us_symbols:
                # The legacy symbol-only endpoint cannot distinguish venues.
                return {"status":"UNAVAILABLE","live":False,"quote":None,"attempts":[],
                        "notice":"Ambiguous Indian/US symbol mapping; use an unambiguous instrument identity.","reason":"AMBIGUOUS_MARKET_IDENTITY"}
            self.adapters = [
                ("UPSTOX", adapters[0][1], upstox_allowed and symbol in mapping),
                ("POLYGON", adapters[1][1], polygon_allowed and symbol in us_symbols),
            ]
            return super().quote(symbol, max_age_seconds)
    return SymbolScopedRouter(adapters, breaker=quote_breaker)

def quote_status(symbol, max_age_seconds=60):
    result = configured_router().quote(symbol, max_age_seconds)
    # Validated quote != streaming subscription; do not claim an active streaming feed.
    result["transport"] = "AUTHORIZED_READ_ONLY_HTTP" if result["status"] == "VALIDATED" else "NONE"
    result["live_feed_verified"] = False
    return result

def provider_status():
    return {"providers": [
        {"code":"UPSTOX","configured":bool(os.getenv("UPSTOX_ACCESS_TOKEN")) and bool(_mapping()),
         "authorization_gate":os.getenv("ATLAS_UPSTOX_QUOTES_AUTHORIZED", "false").lower()=="true"},
        {"code":"POLYGON","configured":bool(os.getenv("ATLAS_POLYGON_API_KEY")),
         "authorization_gate":os.getenv("ATLAS_POLYGON_QUOTES_AUTHORIZED", "false").lower()=="true"}],
        "automatic_fallback_available": False, "streaming_verified": False,
        "http_recovery":quote_recovery.status(),
        "circuits":[quote_breaker.status(name) for name in ("UPSTOX","POLYGON")],
        "notice":"Quote requests require independently authorized credentials. Indian and US instruments cannot substitute for one another; a same-market backup is not configured."}
