"""Opt-in local readiness observation scheduler; never accesses external feeds."""
import asyncio
from datetime import datetime, timezone
import os
from .data_readiness import readiness
from .reliability_incidents import record_snapshot

CODES = {
    "NOT_IMPORTED": "MISSING",
    "STALE_DATA": "STALE",
    "FUTURE_TIMESTAMP": "FUTURE_TIMESTAMP",
    "INVALID_TIMESTAMP": "STORAGE_ERROR",
    "STORAGE_UNAVAILABLE": "STORAGE_ERROR",
}
MIN_INTERVAL = 60
MAX_INTERVAL = 86400

def config(environ=None):
    env = os.environ if environ is None else environ
    enabled = env.get("ATLAS_READINESS_MONITOR_ENABLED", "false").lower() == "true"
    raw = env.get("ATLAS_READINESS_MONITOR_INTERVAL_SECONDS", "900")
    try:
        interval = int(raw)
    except (TypeError, ValueError):
        return {"enabled": False, "interval_seconds": None, "blocker": "INVALID_MONITOR_INTERVAL"}
    if interval < MIN_INTERVAL or interval > MAX_INTERVAL:
        return {"enabled": False, "interval_seconds": None, "blocker": "INVALID_MONITOR_INTERVAL"}
    return {"enabled": enabled, "interval_seconds": interval,
            "blocker": None if enabled else "MONITOR_DISABLED_BY_DEFAULT"}

def observe_once():
    snapshot = readiness()
    issues = [{"dataset": row["code"], "code": CODES[row["status"]]}
              for row in snapshot["datasets"] if row["status"] in CODES]
    # No verified market-data provider is connected; do not clear this incident.
    issues.append({"dataset": "MARKET_DATA", "code": "UNVERIFIED_SOURCE"})
    result = record_snapshot(issues)
    return {**result, "readiness_generated_at": snapshot["generated_at"],
            "source": "SERVER_COMPUTED_LOCAL_READINESS"}

class Monitor:
    def __init__(self):
        self.task = None
        self.last_success = None
        self.last_error = None
        self.runs = 0

    async def start(self):
        cfg = config()
        if cfg["enabled"] and self.task is None:
            self.task = asyncio.create_task(self._loop(cfg["interval_seconds"]))

    async def stop(self):
        if self.task is not None:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

    async def _loop(self, interval):
        while True:
            try:
                # DB and filesystem operations run off the event loop.
                await asyncio.to_thread(observe_once)
                self.runs += 1
                self.last_success = datetime.now(timezone.utc).isoformat()
                self.last_error = None
            except Exception:
                # Avoid exposing filesystem paths, secrets or exception messages.
                self.last_error = "LOCAL_READINESS_OBSERVATION_FAILED"
            await asyncio.sleep(interval)

    def status(self):
        cfg = config()
        return {**cfg, "running": self.task is not None and not self.task.done(),
                "completed_runs": self.runs, "last_success_at": self.last_success,
                "last_error_code": self.last_error,
                "live_feed_connected": False, "automatic_market_collection_enabled": False,
                "scope": "LOCAL_READINESS_ONLY"}

monitor = Monitor()
