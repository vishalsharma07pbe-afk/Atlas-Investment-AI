"""Read-only authorized quote adapters; never submit orders or silently invent timestamps."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal, InvalidOperation
import json
import os
import re
import sqlite3
from urllib.parse import urlsplit
from . import quote_recovery
from .upstox_http_identity import USER_AGENT
import httpx
from urllib.parse import quote, urlencode
from .provider_router import Quote, ProviderFailure, ReadOnlyRouter, CircuitBreaker

SYMBOL_RE = re.compile(r"^[A-Z0-9._&-]{1,40}$")
KEY_RE = re.compile(r"^[A-Z0-9_|.-]{3,120}$")
DEFAULT_TIMEOUT = 5
# Circuit state survives separate HTTP requests within this process.
quote_breaker = CircuitBreaker()

def _request(url, headers, *, payload=None):
    provider={"api.upstox.com":"UPSTOX","api.polygon.io":"POLYGON","api.dhan.co":"DHAN"}.get(urlsplit(url).hostname)
    # The only POST supported by this market-data transport is this fixed
    # read-only quote endpoint. Never forward arbitrary paths or order requests.
    if provider=="DHAN" and (url!="https://api.dhan.co/v2/marketfeed/quote" or payload is None) or provider!="DHAN" and payload is not None:
        raise ProviderFailure("PROVIDER_REQUEST_FAILED")
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
        safe_headers = {**headers, "User-Agent": USER_AGENT if provider=="UPSTOX" else "ATLAS-Research/1.0"}
        if provider=="DHAN":
            response=httpx.post(url,headers=safe_headers,json=payload,timeout=DEFAULT_TIMEOUT,follow_redirects=False)
        else:
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
            raise ProviderFailure("PROVIDER_HTTP_FAILURE" if response.status_code>=500 else "PROVIDER_REQUEST_REJECTED")
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

def dhan_quote(symbol,upstox_key,security_id,token,client_id,*,confirmed_ist=False):
    """Optional read-only quote fallback for one operator-verified exact EQ identity."""
    match=re.fullmatch(r"(NSE_EQ|BSE_EQ)\|INE[A-Z0-9]{9}",upstox_key)
    if (not SYMBOL_RE.fullmatch(symbol) or not match or type(security_id) is not int
        or not 0<security_id<=2_147_483_647 or not token or not client_id):
        raise ProviderFailure("INVALID_DHAN_CONFIGURATION")
    segment=match.group(1)
    body=_request("https://api.dhan.co/v2/marketfeed/quote",
        {"access-token":token,"client-id":client_id,"Accept":"application/json","Content-Type":"application/json"},
        payload={segment:[security_id]})
    data=body.get("data")
    if body.get("status")!="success" or not isinstance(data,dict) or set(data)!={segment}:
        raise ProviderFailure("DHAN_INSTRUMENT_MISMATCH")
    rows=data[segment]
    if not isinstance(rows,dict) or set(rows)!={str(security_id)} or not isinstance(rows[str(security_id)],dict):
        raise ProviderFailure("DHAN_INSTRUMENT_MISMATCH")
    item=rows[str(security_id)]
    stamp=item.get("last_trade_time")
    # Dhan's REST example is a timezone-less DD/MM/YYYY string. Do not
    # guess its timezone: accept explicit offset, or require separate operator
    # confirmation of this exact format and IST semantics before using it.
    try:
        if isinstance(stamp,str) and re.fullmatch(r"[0-9]{2}/[0-9]{2}/[0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2}",stamp):
            if not confirmed_ist:
                raise ProviderFailure("DHAN_TIMESTAMP_UNVERIFIED")
            observed=datetime.strptime(stamp,"%d/%m/%Y %H:%M:%S").replace(tzinfo=ZoneInfo("Asia/Kolkata")).astimezone(timezone.utc)
        elif isinstance(stamp,str) and not stamp.isdigit():
            observed=_timestamp(stamp)
        else:
            raise ProviderFailure("DHAN_TIMESTAMP_UNVERIFIED")
    except (ValueError,TypeError):
        raise ProviderFailure("DHAN_TIMESTAMP_UNVERIFIED") from None
    return Quote(symbol=symbol,price=_price(item.get("last_price")),observed_at=observed,provider="DHAN")


def _dhan_mapping(mapping):
    # The provider security ID is intentionally not inferred from the symbol.
    # The operator must independently verify the corresponding venue and ISIN
    # against Dhan's security master. Match the existing canonical Upstox key.
    raw=os.getenv("ATLAS_DHAN_SYMBOL_MAP","{}")
    if len(raw)>40000:
        return {}
    try:
        parsed=json.loads(raw)
    except (ValueError,TypeError):
        return {}
    if not isinstance(parsed,dict) or len(parsed)>300:
        return {}
    result={}
    for symbol,row in parsed.items():
        if (not isinstance(row,dict) or set(row)!={"upstox_key","security_id"} or symbol not in mapping
            or row["upstox_key"]!=mapping[symbol]
            or not re.fullmatch(r"(NSE_EQ|BSE_EQ)\|INE[A-Z0-9]{9}",mapping[symbol])
            or type(row["security_id"]) is not int or not 0<row["security_id"]<=2_147_483_647):
            continue
        result[symbol]=row["security_id"]
    # A single venue/security ID must not map to conflicting canonical ISINs.
    from collections import Counter
    counts=Counter((mapping[s].split("|")[0],v) for s,v in result.items())
    return {s:v for s,v in result.items() if counts[(mapping[s].split("|")[0],v)]==1}


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
    dhan_mapping=_dhan_mapping(mapping)
    dhan_token=os.getenv("ATLAS_DHAN_ACCESS_TOKEN","")
    dhan_client=os.getenv("ATLAS_DHAN_CLIENT_ID","")
    dhan_ist=os.getenv("ATLAS_DHAN_QUOTE_IST_CONFIRMED","false").lower()=="true"
    dhan_allowed=(os.getenv("ATLAS_DHAN_QUOTES_AUTHORIZED","false").lower()=="true"
                  and bool(dhan_token.strip()) and bool(dhan_client.strip()) and bool(dhan_mapping))
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
    # Disabled-by-default preserves the existing two-provider response contract.
    if dhan_allowed:
        adapters.insert(1,("DHAN",lambda s:dhan_quote(s,mapping[s],dhan_mapping[s],dhan_token,dhan_client,confirmed_ist=dhan_ist),True))
    # Route eligibility is checked per requested symbol, not merely per provider.
    class SymbolScopedRouter(ReadOnlyRouter):
        def quote(self, symbol, max_age_seconds=60):
            if symbol in mapping and symbol in us_symbols:
                # The legacy symbol-only endpoint cannot distinguish venues.
                return {"status":"UNAVAILABLE","live":False,"quote":None,"attempts":[],
                        "notice":"Ambiguous Indian/US symbol mapping; use an unambiguous instrument identity.","reason":"AMBIGUOUS_MARKET_IDENTITY"}
            self.adapters = [(name,fetch,enabled and (symbol in mapping if name=="UPSTOX"
                              else symbol in dhan_mapping if name=="DHAN" else symbol in us_symbols))
                             for name,fetch,enabled in adapters]
            return super().quote(symbol, max_age_seconds)
    return SymbolScopedRouter(adapters, breaker=quote_breaker)

def quote_status(symbol, max_age_seconds=60):
    result = configured_router().quote(symbol, max_age_seconds)
    # Validated quote != streaming subscription; do not claim an active streaming feed.
    result["transport"] = "AUTHORIZED_READ_ONLY_HTTP" if result["status"] == "VALIDATED" else "NONE"
    result["live_feed_verified"] = False
    return result

def provider_status():
    dhan_mapping=_dhan_mapping(_mapping())
    dhan_configured=bool(os.getenv("ATLAS_DHAN_ACCESS_TOKEN","").strip() and os.getenv("ATLAS_DHAN_CLIENT_ID","").strip() and dhan_mapping)
    dhan_gate=os.getenv("ATLAS_DHAN_QUOTES_AUTHORIZED","false").lower()=="true"
    return {"providers": [
        {"code":"UPSTOX","configured":bool(os.getenv("UPSTOX_ACCESS_TOKEN")) and bool(_mapping()),
         "authorization_gate":os.getenv("ATLAS_UPSTOX_QUOTES_AUTHORIZED", "false").lower()=="true"},
        {"code":"POLYGON","configured":bool(os.getenv("ATLAS_POLYGON_API_KEY")),
         "authorization_gate":os.getenv("ATLAS_POLYGON_QUOTES_AUTHORIZED", "false").lower()=="true"},
        {"code":"DHAN","configured":dhan_configured,"authorization_gate":dhan_gate,
         "mapped_symbol_count":len(dhan_mapping),"naive_timestamp_ist_confirmed":os.getenv("ATLAS_DHAN_QUOTE_IST_CONFIRMED","false").lower()=="true"}],
        "automatic_fallback_available": False, "same_market_fallback_configured":dhan_configured and dhan_gate,
        "streaming_verified": False,
        "http_recovery":quote_recovery.status(),
        "circuits":[quote_breaker.status(name) for name in ("UPSTOX","POLYGON","DHAN")],
        "notice":"Optional same-market Dhan HTTP fallback requires independently verified mappings, quote entitlement and timestamp semantics. Configuration does not prove live availability. Indian and US instruments cannot substitute for one another."}
