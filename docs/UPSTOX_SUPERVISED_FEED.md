# Explicitly supervised Upstox feed

The intelligence service now has an opt-in feed supervisor and WebSocket connection lifecycle callbacks. When a subscribed socket is open and the subscription message is sent, connection state becomes true; on any disconnect, reconnect, shutdown or task cancellation, connection state is reset and cached quotes are cleared. A price is shown only when a validated provider trade is within the freshness window.

**Default: disabled.** Local operator must set all of the following in the intelligence service environment:
- `ATLAS_UPSTOX_FEED_ENABLED=true`
- `ATLAS_UPSTOX_INSTRUMENT_KEYS=NSE_EQ|<verified-ISIN>,...`
- `MARKET_DATA_PROVIDER=UPSTOX`
- `UPSTOX_ACCESS_TOKEN` (set only locally; never commit)
- `MARKET_DATA_USAGE_RIGHTS_CONFIRMED=true`
- `MARKET_DATA_ENTITLEMENT_CONFIRMED=true`

The supervisor starts at FastAPI startup and cancels at shutdown. Keys must be from a verified, authorized instrument registry, not guessed. It never performs trades. Signed WSS URLs and tokens remain server-side.

**Limitations:** This code has mocked transport tests, not an authenticated real Upstox session. The local account must be authorized and tested. The live feed's market session, provider licensing, schema evolution and deployment-specific rate limits must be independently validated. Do not interpret an open WebSocket alone as proof of an accurate quote.
