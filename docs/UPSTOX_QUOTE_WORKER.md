# Upstox quote worker and fail-closed cache

This module connects the existing V3 binary transport interface to the decoder, with an in-memory per-instrument cache, timestamp validation, duplicate/out-of-order trade rejection and read-only diagnostics.

The worker requires the provider selection, access token, data usage rights and entitlement to be confirmed. No browser endpoint can start it or supply credentials. Worker is **not launched automatically**. A future transport lifecycle hook must establish real connected state; currently the worker deliberately leaves `connected=false`, so no quote can be advertised as live. This is a safety boundary, not a working live feed.

The API `GET /api/v1/intelligence/providers/upstox/quote-status` exposes aggregate counters and readiness blockers without credentials, signed URLs or prices. The instrument quote endpoint returns only a verified LIVE quote; otherwise it returns an unavailable/stale status with no price.

Next: integrate lifecycle callbacks and supervised startup/shutdown, subscription registry, market session checks, quote publication and UI streaming. Never use test fixture values as market prices.
