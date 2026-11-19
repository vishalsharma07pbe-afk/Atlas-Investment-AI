"""Authenticated internal SSE payloads backed only by the supervised quote cache.

These generators never call a provider. The Upstox WebSocket worker supplies the
cache; SSE merely forwards a new validated tick to an authenticated Spring relay.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from .market_indices import INDEXES
from .upstox_quote_worker import quote_worker


def index_snapshot() -> dict:
    items=[]
    for label,key in INDEXES:
        current=quote_worker.cache.snapshot(key)
        quote=current.get("quote")
        if current.get("status")!="LIVE" or not quote:
            continue
        items.append({
            "label":label,
            "instrument_key":key,
            "price":quote["last_traded_price"],
            "change":quote.get("change",0.0),
            "change_percent":quote.get("change_percent",0.0),
            "as_of":quote["traded_at"],
            "freshness":"LIVE",
            "age_seconds":max(0,int(quote.get("age_ms",0)/1000)),
        })
    if not items:
        return {"status":"UNAVAILABLE","source":"UPSTOX_V3_STREAM",
                "reason":"FEED_DISCONNECTED_OR_NO_FRESH_TICK","items":[],
                "notice":"Waiting for a fresh, validated provider tick."}
    return {"status":"AVAILABLE","source":"UPSTOX_V3_STREAM","items":items,
            "notice":"Push updates from the authorized Upstox WebSocket feed."}


async def changed_events(snapshot,*,interval:float=.25,heartbeat_seconds:float=15.0) -> AsyncIterator[str]:
    """Emit changed JSON payloads and bounded heartbeats for proxy-safe SSE."""
    previous=None
    heartbeat=0.0
    while True:
        payload=snapshot()
        encoded=json.dumps(payload,separators=(",",":"),sort_keys=True)
        identity=json.dumps({
            "status":payload.get("status"),
            "reason":payload.get("reason"),
            "items":[(x.get("instrument_key"),x.get("as_of"),x.get("price"))
                     for x in payload.get("items",[])],
        },separators=(",",":"),sort_keys=True)
        if identity!=previous:
            previous=identity
            heartbeat=0.0
            yield f"event: quote\ndata: {encoded}\n\n"
        elif heartbeat>=heartbeat_seconds:
            heartbeat=0.0
            yield ": keep-alive\n\n"
        await asyncio.sleep(interval)
        heartbeat+=interval


def instrument_snapshot(instrument_key:str) -> dict:
    return quote_worker.cache.snapshot(instrument_key)
