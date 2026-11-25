"""Bounded, read-only Upstox quote lookup for a registry-selected instrument."""
from datetime import datetime, timezone
import re

from fastapi import HTTPException

from .config import settings
from .multi_provider_quotes import ProviderFailure, upstox_quote, _price, _timestamp
from .upstox_quote_worker import quote_worker

SYMBOL = re.compile(r"^[A-Z0-9._&-]{1,40}$")
KEY = re.compile(r"^(NSE_EQ|BSE_EQ)\|[A-Z0-9]{6,24}$")


def current_quote(symbol: str, instrument_key: str) -> dict:
    symbol = symbol.strip().upper()
    if not SYMBOL.fullmatch(symbol) or not KEY.fullmatch(instrument_key):
        raise HTTPException(status_code=422, detail="Select a valid NSE/BSE equity instrument")
    if not (settings.provider == "UPSTOX" and settings.licensed_data_access and
            settings.entitlement_confirmed and settings.upstox_token):
        raise HTTPException(status_code=503, detail="Upstox quote access is not configured")
    try:
        quote = upstox_quote(symbol, instrument_key, settings.upstox_token)
    except ProviderFailure as exc:
        fallback=_stream_fallback(symbol,instrument_key)
        if fallback is not None:
            return fallback
        # Do not disclose arbitrary exception text or provider response bodies.
        code=str(exc)
        if code not in {"PROVIDER_ACCESS_REJECTED","PROVIDER_RATE_LIMITED","PROVIDER_RECOVERY_COOLDOWN",
                        "PROVIDER_REQUEST_FAILED","PROVIDER_HTTP_FAILURE","RECOVERY_STORAGE_UNAVAILABLE"}:
            code="PROVIDER_QUOTE_UNAVAILABLE"
        raise HTTPException(status_code=502, detail=code) from None
    age = (datetime.now(timezone.utc) - quote.observed_at.astimezone(timezone.utc)).total_seconds()
    freshness = "FRESH" if 0 <= age <= 300 else "STALE"
    if freshness=="STALE":
        fallback=_stream_fallback(symbol,instrument_key)
        if fallback is not None:
            return fallback
    if age<0:
        raise HTTPException(status_code=502,detail="PROVIDER_QUOTE_UNAVAILABLE")
    return {
        "status": freshness,
        "symbol": quote.symbol,
        "instrument_key": instrument_key,
        "price": quote.price,
        "as_of": quote.observed_at.isoformat(),
        "age_seconds": max(0, round(age)),
        "source": "UPSTOX",
        "transport": "AUTHORIZED_READ_ONLY_HTTP",
        "live": freshness == "FRESH",
        "live_feed_verified": False,
        "notice": "Read-only provider quote; fresh HTTP observation is not streaming verification. No order execution.",
    }


def _stream_fallback(symbol,key):
    """Only exact actively subscribed keys from the connected authorized worker."""
    if not quote_worker.running or key not in quote_worker.active_keys:
        return None
    snapshot=quote_worker.cache.snapshot(key)
    item=snapshot.get("quote")
    if snapshot.get("status")!="LIVE" or not isinstance(item,dict) or item.get("instrument_key")!=key:
        return None
    try:
        observed=_timestamp(item.get("traded_at"))
        age=(datetime.now(timezone.utc)-observed).total_seconds()
        if not 0<=age<=quote_worker.cache.policy.max_tick_age_seconds:
            return None
        price=_price(item.get("last_traded_price"))
    except (ProviderFailure,ValueError,TypeError,OverflowError):
        return None
    return {"status":"FRESH","symbol":symbol,"instrument_key":key,
            "price":price,"as_of":observed.isoformat(),"age_seconds":round(age),
            "source":"UPSTOX","transport":"AUTHORIZED_UPSTOX_V3_STREAM",
            "live":True,"live_feed_verified":True,"fallback_used":True,
            "notice":"Fresh subscribed observation from the same Upstox instrument after HTTP quote unavailable or stale. Not an independent provider."}
