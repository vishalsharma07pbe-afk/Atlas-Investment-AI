"""Read-only provider feed SLO assessment. No network calls or authorization changes."""
from datetime import datetime, timezone

def assess_feed(status: dict, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    blockers = status.get("blockers") or []
    configured = status.get("configuration_status") == "CONFIGURED"
    running = status.get("worker_running") is True
    connected = status.get("transport_connected") is True
    frames = status.get("frames_processed", 0)
    rejected = status.get("rejected_entries", 0)
    if not isinstance(frames, int) or isinstance(frames, bool) or frames < 0:
        frames = 0
    if not isinstance(rejected, int) or isinstance(rejected, bool) or rejected < 0:
        rejected = 0
    if not configured:
        state, reason = "BLOCKED", "PROVIDER_AUTHORIZATION_NOT_VERIFIED"
    elif not running:
        state, reason = "STOPPED", "WORKER_NOT_RUNNING"
    elif not connected:
        state, reason = "DISCONNECTED", "TRANSPORT_NOT_CONNECTED"
    elif frames == 0:
        state, reason = "NO_DATA", "NO_FEED_FRAMES"
    elif rejected > 0 and rejected >= frames:
        state, reason = "DEGRADED", "REJECTED_FRAME_THRESHOLD"
    else:
        state, reason = "CONNECTED_UNVERIFIED", "PER_INSTRUMENT_FRESHNESS_REQUIRED"
    return {
        "generated_at": now.isoformat(), "provider": "UPSTOX",
        "state": state, "reason": reason,
        "transport_connected": connected, "worker_running": running,
        "frames_processed": frames, "rejected_entries": rejected,
        "cached_instruments": max(0, int(status.get("cached_instruments", 0))) if isinstance(status.get("cached_instruments", 0), int) else 0,
        "live_prices_verified": False,
        "entitlement_verified": False,
        "automatic_collection_authorized_by_this_check": False,
        "blocker_codes": [str(x)[:100] for x in blockers if isinstance(x, str)][:20],
        "note": "Transport health does not establish data rights, instrument freshness, or quote accuracy.",
    }
