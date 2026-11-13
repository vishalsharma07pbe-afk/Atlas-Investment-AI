"""Explicit opt-in lifecycle for read-only market feed, never order execution."""
import asyncio
import os
from .upstox_quote_worker import quote_worker
from .upstox_stream import StreamPolicy,subscription_request
from .config import settings

class FeedSupervisor:
    def __init__(self,worker=quote_worker):
        self.worker=worker
        self.task=None
        self.last_result=None

    async def start(self,*,enabled:bool,keys:list[str],token:str|None,
                    provider:str,rights:bool,entitlement:bool):
        if not enabled:return {"status":"DISABLED"}
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
        self.task=asyncio.create_task(runner(),name="atlas-upstox-feed")
        return {"status":"STARTING"}

    async def stop(self):
        self.worker.shutdown()
        if self.task and not self.task.done():
            self.task.cancel()
            try:await self.task
            except asyncio.CancelledError:pass
        self.task=None

    def status(self):
        return {"supervised_task_running":bool(self.task and not self.task.done()),
                "last_result":self.last_result}

feed_supervisor=FeedSupervisor()

async def startup_feed():
    enabled=os.getenv("ATLAS_UPSTOX_FEED_ENABLED","false").lower()=="true"
    keys=[x.strip() for x in os.getenv("ATLAS_UPSTOX_INSTRUMENT_KEYS","").split(",") if x.strip()]
    return await feed_supervisor.start(enabled=enabled,keys=keys,token=settings.upstox_token,
                                      provider=settings.provider,rights=settings.licensed_data_access,
                                      entitlement=settings.entitlement_confirmed)
