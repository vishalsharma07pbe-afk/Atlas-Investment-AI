# ATLAS read-only Upstox live-feed operations

## What is implemented
- Verified local instrument ID selection (the backend registry is authoritative; no ticker guessing).
- Upstox V3 feed authorization, signed WebSocket connection, binary LTPC subscription, bounded Protobuf decoding and timestamp validation.
- Supervised startup/shutdown, retry limits, disconnect-safe cache, quote/status endpoints and five-second dashboard refresh.
- Fail-closed provider rights/entitlement checks; no trade execution.

## Local configuration
Set `MARKET_DATA_PROVIDER=UPSTOX`, `MARKET_DATA_USAGE_RIGHTS_CONFIRMED=true`, `MARKET_DATA_ENTITLEMENT_CONFIRMED=true`, `UPSTOX_ACCESS_TOKEN` and `ATLAS_UPSTOX_FEED_ENABLED=true` **only if these facts are true**. Set `ATLAS_UPSTOX_INSTRUMENT_IDS=123,456` to select active NSE instruments already imported into the backend registry. Alternatively set `ATLAS_UPSTOX_INSTRUMENT_KEYS` only when their provider mapping is independently verified. Do not configure both selection methods. Restart the intelligence service. Never commit or paste bearer tokens.

Inspect `/api/v1/intelligence/providers/upstox/quote-status` for supervisor status, subscription count, connection status and counters. Select a matching instrument in Stock Explorer to see its quote status. During market closure or without fresh provider ticks, quotes will not show as live.

## Acceptance checklist for a real account
1. Confirm Upstox account market-feed entitlement and permitted personal-use data rights.
2. Import a licensed instrument master and select an active NSE equity in the registry.
3. Configure token and flags locally, then start Docker Compose.
4. Confirm authorization and WebSocket subscription; validate LTPC field mappings and timestamps against actual provider data.
5. Confirm quote becomes LIVE only after a valid fresh trade, then STALE when it ages and UNAVAILABLE after disconnect.
6. Confirm reconnect clears old quotes, resubscribes and uses a newly authorized URI.
7. Confirm no tokens, signed URIs or raw frames appear in logs or browser APIs.

**Cannot be claimed complete without account testing:** Actual Upstox session, provider entitlement, real-time market-session behavior and correctness of decoded prices. There is no automatic order execution.
