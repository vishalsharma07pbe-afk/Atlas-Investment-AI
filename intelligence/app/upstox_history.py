"""Explicitly authorized, read-only Upstox daily candle import. Never enables unattended collection."""
from datetime import date, datetime, timezone
from urllib.parse import quote
import os
from .multi_provider_quotes import _mapping, _request, ProviderFailure
from .ohlcv_store import import_candles

def _enabled():
    return (os.getenv("ATLAS_UPSTOX_HISTORICAL_AUTHORIZED","false").lower()=="true"
            and os.getenv("MARKET_DATA_USAGE_RIGHTS_CONFIRMED","false").lower()=="true"
            and os.getenv("MARKET_DATA_ENTITLEMENT_CONFIRMED","false").lower()=="true"
            and bool(os.getenv("UPSTOX_ACCESS_TOKEN")))

def parse_upstox_candles(body):
    if not isinstance(body,dict) or body.get("status")!="success":
        raise ProviderFailure("INVALID_CANDLE_RESPONSE")
    data=body.get("data")
    rows=data.get("candles") if isinstance(data,dict) else None
    if not isinstance(rows,list) or not 1<=len(rows)<=5000:
        raise ProviderFailure("INVALID_CANDLE_RESPONSE")
    normalized=[]
    for row in rows:
        if not isinstance(row,list) or len(row)<6:
            raise ProviderFailure("INVALID_CANDLE_ROW")
        timestamp,op,hi,lo,cl,volume=row[:6]
        if not isinstance(timestamp,str):
            raise ProviderFailure("INVALID_CANDLE_TIMESTAMP")
        try:
            observed=datetime.fromisoformat(timestamp.replace("Z","+00:00"))
        except ValueError as exc:
            raise ProviderFailure("INVALID_CANDLE_TIMESTAMP") from exc
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise ProviderFailure("INVALID_CANDLE_TIMESTAMP")
        normalized.append({"date":observed.date().isoformat(),"open":op,"high":hi,
                           "low":lo,"close":cl,"volume":volume})
    return normalized

def import_upstox_daily(symbol, market, start_date, end_date):
    if not _enabled():
        return {"status":"BLOCKED_AUTHORIZATION","imported":False}
    if market not in ("NSE","BSE"):
        raise ValueError("UNSUPPORTED_MARKET")
    mapping=_mapping()
    instrument_key=mapping.get(symbol)
    if not instrument_key or not instrument_key.startswith(market+"_EQ|"):
        raise ValueError("MISSING_VERIFIED_INSTRUMENT_MAPPING")
    try:
        start=date.fromisoformat(start_date)
        end=date.fromisoformat(end_date)
    except (ValueError,TypeError) as exc:
        raise ValueError("INVALID_DATE_RANGE") from exc
    if start>end or end>datetime.now(timezone.utc).date() or (end-start).days>365:
        raise ValueError("INVALID_DATE_RANGE")
    # Upstox historical v3: interval unit days, interval 1, to_date, from_date.
    url=("https://api.upstox.com/v3/historical-candle/"
         +quote(instrument_key,safe="")+"/days/1/"+end.isoformat()+"/"+start.isoformat())
    body=_request(url,{"Authorization":"Bearer "+os.environ["UPSTOX_ACCESS_TOKEN"],
                       "Accept":"application/json"})
    rows=parse_upstox_candles(body)
    if any(not start<=date.fromisoformat(row["date"])<=end for row in rows):
        raise ProviderFailure("CANDLE_OUTSIDE_REQUESTED_RANGE")
    result=import_candles(symbol,market,"UPSTOX",rows)
    return {**result,"provider":"UPSTOX","instrument_key":instrument_key,
            "range_start":start.isoformat(),"range_end":end.isoformat(),
            "live_feed_connected":False}
