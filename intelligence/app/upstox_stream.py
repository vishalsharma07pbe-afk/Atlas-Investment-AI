"""Upstox V3 stream safety gates and tick freshness validation.

Transport and protobuf decoding must be integrated before live collection is enabled.
No trades, token exposure, or fabricated quotes.
"""
from datetime import datetime, timezone
from math import isfinite
from urllib.parse import urlsplit
from pydantic import BaseModel, Field

class StreamPolicy(BaseModel):
    max_tick_age_seconds: int = Field(default=15, ge=1, le=300)
    max_future_skew_seconds: int = Field(default=5, ge=0, le=60)
    max_subscriptions: int = Field(default=2000, ge=1, le=2000)

def validate_redirect(uri: str) -> str:
    """Accept only secure Upstox-owned WSS endpoints; never log the signed URI."""
    parsed = urlsplit(uri)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "wss" or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("Invalid secure feed endpoint")
    if host != "upstox.com" and not host.endswith(".upstox.com"):
        raise ValueError("Untrusted feed endpoint")
    if parsed.port not in (None, 443):
        raise ValueError("Unexpected feed port")
    return uri

def subscription_request(keys: list[str], policy: StreamPolicy, guid: str) -> dict:
    if not guid or len(guid)>100:
        raise ValueError("Invalid request identifier")
    if not keys or len(keys)>policy.max_subscriptions or len(set(keys))!=len(keys):
        raise ValueError("Invalid subscription count or duplicate keys")
    for key in keys:
        if not isinstance(key,str) or not key.startswith(("NSE_EQ|","BSE_EQ|","NSE_INDEX|","BSE_INDEX|")) or len(key)>100:
            raise ValueError("Unsupported instrument key")
    return {"guid":guid,"method":"sub","data":{"mode":"ltpc","instrumentKeys":keys}}

def normalize_tick(instrument_key: str, ltpc: dict, policy: StreamPolicy, now_ms: int | None = None) -> dict:
    """Only accept provider-decoded LTPC values with valid timestamps."""
    if not isinstance(ltpc,dict):
        raise ValueError("Invalid LTPC payload")
    ltp=ltpc.get("ltp")
    if isinstance(ltp,bool) or not isinstance(ltp,(int,float)) or not isfinite(ltp) or ltp<=0:
        raise ValueError("Invalid last traded price")
    try:
        ts=int(ltpc["ltt"])
    except (KeyError,ValueError,TypeError) as exc:
        raise ValueError("Invalid provider trade timestamp") from exc
    now_ms=now_ms if now_ms is not None else int(datetime.now(timezone.utc).timestamp()*1000)
    age=now_ms-ts
    if age < -policy.max_future_skew_seconds*1000:
        raise ValueError("Future-dated trade")
    if age > policy.max_tick_age_seconds*1000:
        raise ValueError("Stale trade")
    return {"instrument_key":instrument_key,"last_traded_price":float(ltp),
            "traded_at":datetime.fromtimestamp(ts/1000,timezone.utc).isoformat(),
            "age_ms":age,"status":"FRESH","source":"UPSTOX_V3"}

def stream_readiness(configured: bool, authorized: bool, decoder_verified: bool, connected: bool) -> dict:
    blockers=[]
    if not configured: blockers.append("PROVIDER_NOT_CONFIGURED")
    if not authorized: blockers.append("UPSTOX_AUTHORIZATION_REQUIRED")
    if not decoder_verified: blockers.append("V3_PROTOBUF_DECODER_NOT_VERIFIED")
    if not connected: blockers.append("WEBSOCKET_NOT_CONNECTED")
    return {"status":"READY" if not blockers else "BLOCKED",
            "live_quotes_available":not blockers,"blockers":blockers,
            "notice":"No quote is considered live until a validated, timestamped provider tick is received."}
