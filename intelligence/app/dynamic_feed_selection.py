"""Automatically reconcile the read-only Upstox feed with saved equity holdings."""
from __future__ import annotations

import asyncio
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import settings
from .upstox_stream import StreamPolicy, subscription_request
from .upstox_supervisor import feed_supervisor


class DynamicFeedSelection:
    def __init__(self):
        self.task: asyncio.Task | None = None
        self.interval_seconds = max(5, min(300, int(os.getenv("ATLAS_DYNAMIC_FEED_POLL_SECONDS", "10"))))
        self.last_status = {
            "mode": "PORTFOLIO_AUTOMATIC",
            "status": "NOT_STARTED",
            "resolved_count": 0,
            "missing_symbols": [],
        }
        self._lock = asyncio.Lock()

    @property
    def explicit_selection(self) -> bool:
        return bool((os.getenv("ATLAS_UPSTOX_INSTRUMENT_IDS") or "").strip() or
                    (os.getenv("ATLAS_UPSTOX_INSTRUMENT_KEYS") or "").strip())

    def _fetch(self) -> dict:
        token=os.getenv("INTERNAL_SERVICE_TOKEN","")
        if not token:
            raise RuntimeError("INTERNAL_SERVICE_TOKEN_MISSING")
        url=settings.backend_url.rstrip("/")+"/api/v1/internal/feed/equity-subscriptions"
        request=Request(url,headers={"Accept":"application/json","X-Atlas-Service-Token":token})
        try:
            with urlopen(request,timeout=8) as response:
                raw=response.read(1_000_001)
                if response.status!=200 or len(raw)>1_000_000:
                    raise RuntimeError("PORTFOLIO_SELECTION_UNAVAILABLE")
            value=json.loads(raw)
        except (HTTPError,URLError,TimeoutError,OSError,ValueError,json.JSONDecodeError) as exc:
            raise RuntimeError("PORTFOLIO_SELECTION_UNAVAILABLE") from exc
        if not isinstance(value,dict) or not isinstance(value.get("subscriptions"),list):
            raise RuntimeError("PORTFOLIO_SELECTION_INVALID")
        return value

    async def reconcile(self) -> dict:
        async with self._lock:
            if self.explicit_selection:
                self.last_status={"mode":"EXPLICIT_ENV_FALLBACK","status":"MANAGED_AT_STARTUP",
                                  "resolved_count":feed_supervisor.selected_count,"missing_symbols":[]}
                return self.last_status
            if not (settings.provider=="UPSTOX" and settings.upstox_token and
                    settings.licensed_data_access and settings.entitlement_confirmed):
                self.last_status={"mode":"PORTFOLIO_AUTOMATIC","status":"BLOCKED_CONFIGURATION",
                                  "resolved_count":0,"missing_symbols":[]}
                return self.last_status
            try:
                selection=await asyncio.to_thread(self._fetch)
                rows=selection["subscriptions"]
                keys=[row.get("instrument_key") for row in rows if isinstance(row,dict)]
                if any(not isinstance(key,str) for key in keys):
                    raise RuntimeError("PORTFOLIO_SELECTION_INVALID")
                if keys:
                    subscription_request(keys,StreamPolicy(),"dynamic-selection-validation")
                desired=set(keys)
                current=set(feed_supervisor.worker.active_keys)
                if desired!=current:
                    await feed_supervisor.stop()
                    if keys:
                        result=await feed_supervisor.start(enabled=True,keys=keys,
                            token=settings.upstox_token,provider=settings.provider,
                            rights=settings.licensed_data_access,
                            entitlement=settings.entitlement_confirmed)
                    else:
                        result={"status":"IDLE_NO_EQUITY_HOLDINGS"}
                    feed_supervisor.startup_result=result
                else:
                    result={"status":"IN_SYNC" if keys else "IDLE_NO_EQUITY_HOLDINGS"}
                self.last_status={
                    "mode":"PORTFOLIO_AUTOMATIC",
                    "status":result["status"],
                    "holding_symbol_count":int(selection.get("holding_symbol_count",0)),
                    "resolved_count":len(keys),
                    "missing_symbols":[str(x) for x in selection.get("missing_symbols",[])][:100],
                    "poll_seconds":self.interval_seconds,
                }
            except (RuntimeError,ValueError,TypeError) as exc:
                self.last_status={"mode":"PORTFOLIO_AUTOMATIC","status":"RECONCILE_FAILED",
                                  "reason":str(exc),"resolved_count":0,"missing_symbols":[]}
            return self.last_status

    async def _run(self):
        while True:
            await self.reconcile()
            await asyncio.sleep(self.interval_seconds)

    async def start(self):
        if self.task and not self.task.done():
            return
        self.task=asyncio.create_task(self._run(),name="atlas-dynamic-feed-selection")

    async def stop(self):
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        self.task=None


dynamic_feed_selection=DynamicFeedSelection()
