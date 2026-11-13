"""Opt-in read-only quote worker, decoded feed cache and readiness gates.

A quote is never labelled live without a connected, authorized transport,
verified subscribed key, fresh trade timestamp, and confirmed data rights.
"""
import asyncio
from datetime import datetime,timezone
from .upstox_decoder import decode_quotes,DecodeError
from .upstox_transport import reconnecting_stream
from .upstox_stream import StreamPolicy
from .upstox_authorization import authorization_diagnostics

class QuoteCache:
    def __init__(self,policy:StreamPolicy|None=None):
        self.policy=policy or StreamPolicy()
        self.quotes={}
        self.connected=False
        self.last_error=None
        self.frames=0
        self.rejected=0

    def ingest(self,frame:bytes,keys:set[str],now_ms:int|None=None):
        result=decode_quotes(frame,keys,self.policy,now_ms)
        self.frames+=1
        self.rejected+=len(result["rejected"])
        if result["message_type"]!="LIVE_FEED":return result
        for quote in result["quotes"]:
            key=quote["instrument_key"]
            previous=self.quotes.get(key)
            if previous and quote["traded_at"]<previous["traded_at"]:continue
            self.quotes[key]=quote
        return result

    def snapshot(self,key:str,now_ms:int|None=None):
        quote=self.quotes.get(key)
        now_ms=now_ms if now_ms is not None else int(datetime.now(timezone.utc).timestamp()*1000)
        if not self.connected or quote is None:
            return {"status":"UNAVAILABLE","quote":None,"reason":"FEED_DISCONNECTED_OR_NO_TICK"}
        timestamp=datetime.fromisoformat(quote["traded_at"])
        age_ms=now_ms-int(timestamp.timestamp()*1000)
        if age_ms< -self.policy.max_future_skew_seconds*1000 or age_ms>self.policy.max_tick_age_seconds*1000:
            return {"status":"STALE","quote":None,"reason":"TRADE_TIMESTAMP_OUTSIDE_FRESHNESS_WINDOW"}
        return {"status":"LIVE","quote":{**quote,"age_ms":age_ms},"reason":None}

    def diagnostics(self):
        return {"connected":self.connected,"cached_instruments":len(self.quotes),
                "frames_processed":self.frames,"rejected_entries":self.rejected}

class QuoteWorker:
    def __init__(self,cache:QuoteCache|None=None):
        self.cache=cache or QuoteCache()
        self.stop=asyncio.Event()
        self.active_keys=set()
        self.running=False

    async def run(self,token:str,keys:list[str],*,provider:str,rights:bool,
                  entitlement:bool,stream=reconnecting_stream):
        gate=authorization_diagnostics(provider,bool(token and token.strip()),rights,entitlement)
        if gate["status"]!="CONFIGURED":
            return {"status":"BLOCKED","blockers":gate["blockers"]}
        if self.running:raise RuntimeError("Quote worker already running")
        from .upstox_stream import subscription_request
        subscription_request(keys,self.cache.policy,"worker")
        self.running=True
        self.stop.clear()
        self.active_keys=set(keys)
        async def on_connection_change(connected:bool):
            self.cache.connected=connected
            if not connected:self.cache.quotes.clear()
        async def on_frame(frame:bytes):
            try:self.cache.ingest(frame,self.active_keys)
            except (DecodeError,ValueError,OverflowError):
                self.cache.rejected+=1
        try:
            # Connection state is not inferred from a decoded frame alone.
            # The transport needs lifecycle callbacks before a LIVE status is possible.
            if stream is reconnecting_stream:
                result=await stream(token,keys,on_frame,stop=self.stop,
                                    on_connection_change=on_connection_change)
            else:
                result=await stream(token,keys,on_frame,stop=self.stop)
            return result
        finally:
            self.cache.connected=False
            self.cache.quotes.clear()
            self.active_keys.clear()
            self.running=False

    def shutdown(self):
        self.stop.set()
        self.cache.connected=False
        self.cache.quotes.clear()

quote_worker=QuoteWorker()
