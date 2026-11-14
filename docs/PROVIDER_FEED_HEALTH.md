# Provider Feed Health — read-only SLO diagnostics

The Market & Data Health tab now displays Upstox transport state, worker status, frame counts, rejected entries, and cached instrument count. The endpoint `GET /api/v1/intelligence/providers/upstox/feed-health` reuses the existing safe quote-status API. It performs **no network calls**, starts no stream, and never exposes credentials or raw quotes.

States: BLOCKED (provider authorization not configured), STOPPED (worker inactive), DISCONNECTED (transport down), NO_DATA (connected but no frames), DEGRADED (rejected entries at least equal to frames), CONNECTED_UNVERIFIED (transport and frames seen, but instrument freshness and rights still require independent checks). These are *diagnostics*, not service availability guarantees or measured SLO percentages. Counters are process-local and reset on restart.

## Verify
Run `cd intelligence && python3 -m unittest discover -s tests -p 'test_feed_health.py'`; run the full Python CI suite and React build/tests. Open the Market & Data Health tab; the feed should show BLOCKED or STOPPED until a genuinely authorized connection exists. Confirm the endpoint does not disclose tokens and that no trades are possible.

## Blockers and next work
Upstox token/account approval and independent market-data usage rights are not established. This module never upgrades an unverified feed to live. Next implement persistent, timestamped transport observations, bounded outage windows and alerts only after authorization, and test with simulated disconnect/reconnect sequences.
