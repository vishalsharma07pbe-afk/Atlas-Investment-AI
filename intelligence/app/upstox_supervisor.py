"""Explicit opt-in lifecycle for read-only market feed, never order execution."""
import asyncio
import os
from .upstox_quote_worker import quote_worker
from .upstox_stream import StreamPolicy,subscription_request
from .config import settings
from .upstox_feed_selection import parse_ids,resolve_ids,FeedSelectionError
from .market_indices import INDEXES

class FeedSupervisor:
    def __init__(self,worker=quote_worker):
        self.worker=worker
        self.task=None
        self.last_result=None
        self.selected_count=0
        self.startup_result={"status":"NOT_STARTED"}

    async def start(self,*,enabled:bool,keys:list[str],token:str|None,
                    provider:str,rights:bool,entitlement:bool):
        if not enabled:
            return {"status":"DISABLED"}
        if self.task and not self.task.done():return {"status":"ALREADY_RUNNING"}
        if not keys:return {"status":"BLOCKED","blockers":["INSTRUMENT_KEYS_MISSING"]}
        try:subscription_request(keys,StreamPolicy(),"supervisor")
        except ValueError:return {"status":"BLOCKED","blockers":["INVALID_INSTRUMENT_KEYS"]}
        if provider!="UPSTOX" or not token or not rights or not entitlement:
            return {"status":"BLOCKED","blockers":["PROVIDER_CONFIGURATION_INCOMPLETE"]}
        async def runner():
            try:self.last_result=await self.worker.run(token,keys,provider=provider,
                                  rights=rights,entitlement=entitlement)
            except asyncio.CancelledError:raise
            except Exception:
                self.last_result={"status":"FAILED","reason":"FEED_WORKER_UNAVAILABLE"}
            finally:self.worker.shutdown()
        self.selected_count=len(keys)
        self.task=asyncio.create_task(runner(),name="atlas-upstox-feed")
        return {"status":"STARTING"}

    async def stop(self):
        self.worker.shutdown()
        if self.task and not self.task.done():
            self.task.cancel()
            try:await self.task
            except asyncio.CancelledError:pass
        self.task=None
        self.selected_count=0

    def status(self):
        return {"startup":self.startup_result,"selected_instruments":self.selected_count,
                "supervised_task_running":bool(self.task and not self.task.done()),
                "last_result":self.last_result}

feed_supervisor=FeedSupervisor()

async def startup_feed():
    enabled=os.getenv("ATLAS_UPSTOX_FEED_ENABLED","false").lower()=="true"
    if not enabled:return {"status":"DISABLED"}
    raw_ids=os.getenv("ATLAS_UPSTOX_INSTRUMENT_IDS","")
    raw_keys=os.getenv("ATLAS_UPSTOX_INSTRUMENT_KEYS","")
    if raw_ids.strip() and raw_keys.strip():
        feed_supervisor.startup_result={"status":"BLOCKED","blockers":["CONFLICTING_INSTRUMENT_SELECTION"]}
        return feed_supervisor.startup_result
    if not (settings.provider=="UPSTOX" and settings.upstox_token and
            settings.licensed_data_access and settings.entitlement_confirmed):
        feed_supervisor.startup_result={"status":"BLOCKED","blockers":["PROVIDER_CONFIGURATION_INCOMPLETE"]}
        return feed_supervisor.startup_result
    if not raw_ids.strip() and not raw_keys.strip():
        feed_supervisor.startup_result={"status":"AWAITING_PORTFOLIO_SELECTION"}
        return feed_supervisor.startup_result
    try:
        if raw_ids.strip():
            ids=parse_ids(raw_ids)
            keys=await asyncio.to_thread(resolve_ids,ids)
        else:
            keys=[x.strip() for x in raw_keys.split(",") if x.strip()]
        keys=sorted(set(keys)|{key for _,key in INDEXES})
    except FeedSelectionError:
        feed_supervisor.startup_result={"status":"BLOCKED","blockers":["INSTRUMENT_REGISTRY_RESOLUTION_FAILED"]}
        return feed_supervisor.startup_result
    feed_supervisor.startup_result=await feed_supervisor.start(enabled=enabled,keys=keys,token=settings.upstox_token,
                                      provider=settings.provider,rights=settings.licensed_data_access,
                                      entitlement=settings.entitlement_confirmed)
    return feed_supervisor.startup_result
