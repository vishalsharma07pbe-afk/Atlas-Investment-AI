"""Resolve explicit local registry IDs to verified provider keys at startup."""
import asyncio
from .instrument_resolution import resolve_upstox_instrument
from .market_client import backend_json
from .upstox_stream import StreamPolicy,subscription_request

class FeedSelectionError(ValueError):
    pass

def parse_ids(raw:str)->list[int]:
    if not raw.strip():return []
    parts=[x.strip() for x in raw.split(",")]
    if len(parts)>200 or any(not x.isdecimal() or int(x)<=0 for x in parts):
        raise FeedSelectionError("Invalid local instrument IDs")
    ids=[int(x) for x in parts]
    if len(ids)!=len(set(ids)):raise FeedSelectionError("Duplicate local instrument IDs")
    return ids

def resolve_ids(ids:list[int],fetch=backend_json)->list[str]:
    keys=[]
    for instrument_id in ids:
        try:record=fetch(f"/api/v1/instruments/{instrument_id}")
        except Exception:raise FeedSelectionError("Instrument registry unavailable") from None
        if not isinstance(record,dict):raise FeedSelectionError("Invalid registry response")
        result=resolve_upstox_instrument(record)
        if not result["subscription_ready"]:
            raise FeedSelectionError("Registry instrument not eligible for Upstox feed")
        keys.append(result["instrument_key"])
    try:subscription_request(keys,StreamPolicy(),"verified-startup")
    except ValueError:raise FeedSelectionError("Invalid or duplicate provider keys") from None
    return keys
