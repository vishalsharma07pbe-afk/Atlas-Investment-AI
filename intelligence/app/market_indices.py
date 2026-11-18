"""Bounded, read-only snapshots for the dashboard's Indian market index strip."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from .config import settings
from .multi_provider_quotes import ProviderFailure, _request, _timestamp


INDEXES = (
    ("NIFTY 50", "NSE_INDEX|Nifty 50"),
    ("BANK NIFTY", "NSE_INDEX|Nifty Bank"),
    ("SENSEX", "BSE_INDEX|SENSEX"),
    ("NIFTY NEXT 50", "NSE_INDEX|Nifty Next 50"),
    ("NIFTY MIDCAP 100", "NSE_INDEX|NIFTY MIDCAP 100"),
    ("INDIA VIX", "NSE_INDEX|India VIX"),
)


def _number(value, *, positive=False) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ProviderFailure("PROVIDER_SCHEMA_INVALID") from exc
    if not parsed.is_finite() or (positive and parsed <= 0):
        raise ProviderFailure("PROVIDER_SCHEMA_INVALID")
    return parsed


def _unavailable(reason: str) -> dict:
    return {
        "status": "UNAVAILABLE",
        "source": "UPSTOX",
        "reason": reason,
        "items": [],
        "notice": "No index values are shown unless an authorized provider returns them.",
    }


def snapshots() -> dict:
    if not (settings.provider == "UPSTOX" and settings.licensed_data_access and
            settings.entitlement_confirmed and settings.upstox_token):
        return _unavailable("PROVIDER_NOT_CONFIGURED")

    keys = [key for _, key in INDEXES]
    url = "https://api.upstox.com/v3/market-quote/quotes?" + urlencode({
        "instrument_key": ",".join(keys)
    })
    try:
        body = _request(url, {
            "Authorization": "Bearer " + settings.upstox_token,
            "Accept": "application/json",
        })
    except ProviderFailure as exc:
        return _unavailable(str(exc))

    data = body.get("data")
    if body.get("status") != "success" or not isinstance(data, dict):
        return _unavailable("PROVIDER_SCHEMA_INVALID")

    by_token = {
        item.get("instrument_token"): item
        for item in data.values()
        if isinstance(item, dict) and isinstance(item.get("instrument_token"), str)
    }
    now = datetime.now(timezone.utc)
    items = []
    for label, key in INDEXES:
        item = by_token.get(key)
        if not item:
            continue
        try:
            price = _number(item.get("last_price"), positive=True)
            change = _number(item.get("net_change", 0))
            previous_value = item.get("prev_close_price")
            previous = (_number(previous_value, positive=True)
                        if previous_value is not None else price - change)
            if previous <= 0:
                raise ProviderFailure("PROVIDER_SCHEMA_INVALID")
            observed = _timestamp(item.get("last_trade_time"))
        except ProviderFailure:
            continue
        age = max(0, round((now - observed).total_seconds()))
        items.append({
            "label": label,
            "instrument_key": key,
            "price": float(price),
            "change": float(change),
            "change_percent": float(change / previous * 100),
            "as_of": observed.isoformat(),
            "freshness": "LIVE" if age <= 300 else "DELAYED",
            "age_seconds": age,
        })

    if not items:
        return _unavailable("NO_VALID_INDEX_QUOTES")
    return {
        "status": "AVAILABLE",
        "source": "UPSTOX",
        "items": items,
        "notice": "Read-only exchange snapshots. DELAYED can indicate a closed market.",
    }
