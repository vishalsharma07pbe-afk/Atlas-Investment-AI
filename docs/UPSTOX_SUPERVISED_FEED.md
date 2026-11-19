# Explicitly supervised Upstox feed

The intelligence service now has an opt-in feed supervisor and WebSocket connection lifecycle callbacks. When a subscribed socket is open and the subscription message is sent, connection state becomes true; on any disconnect, reconnect, shutdown or task cancellation, connection state is reset and cached quotes are cleared. A price is shown only when a validated provider trade is within the freshness window.

**Default: disabled.** Local operator must set all of the following in the intelligence service environment:
- `ATLAS_UPSTOX_FEED_ENABLED=true`
- `MARKET_DATA_PROVIDER=UPSTOX`
- `UPSTOX_ACCESS_TOKEN` (set only locally; never commit)
- `MARKET_DATA_USAGE_RIGHTS_CONFIRMED=true`
- `MARKET_DATA_ENTITLEMENT_CONFIRMED=true`

The supervisor starts at FastAPI startup and cancels at shutdown. Keys must be from a verified, authorized instrument registry, not guessed. It never performs trades. Signed WSS URLs and tokens remain server-side.

ATLAS automatically keeps the supported market indices and saved equity holdings subscribed. Opening a mapped stock adds a temporary subscription and closing it removes that request. `ATLAS_UPSTOX_INSTRUMENT_IDS` or `ATLAS_UPSTOX_INSTRUMENT_KEYS` may still be used as an explicit operator fallback, but neither is required for the automatic mode.

Fresh validated ticks are forwarded through the Spring backend's authenticated `/api/v1/live/...` SSE endpoints. The browser uses native automatic reconnection and retains the last clearly timestamped value while reconnecting; it does not issue high-frequency REST requests.

**Limitations:** This code has mocked transport tests, not an authenticated real Upstox session. The local account must be authorized and tested. The live feed's market session, provider licensing, schema evolution and deployment-specific rate limits must be independently validated. Do not interpret an open WebSocket alone as proof of an accurate quote.
