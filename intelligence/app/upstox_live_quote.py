"""Bounded, read-only Upstox quote lookup for a registry-selected instrument."""
from datetime import datetime, timezone
import re

from fastapi import HTTPException

from .config import settings
from .multi_provider_quotes import ProviderFailure, upstox_quote

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
        raise HTTPException(status_code=502, detail=str(exc)) from None
    age = (datetime.now(timezone.utc) - quote.observed_at.astimezone(timezone.utc)).total_seconds()
    freshness = "FRESH" if -5 <= age <= 300 else "STALE"
    return {
        "status": freshness,
        "symbol": quote.symbol,
        "instrument_key": instrument_key,
        "price": quote.price,
        "as_of": quote.observed_at.isoformat(),
        "age_seconds": max(0, round(age)),
        "source": "UPSTOX",
        "live": freshness == "FRESH",
        "notice": "Read-only provider quote; no order execution.",
    }
