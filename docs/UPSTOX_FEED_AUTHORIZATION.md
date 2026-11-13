# Upstox V3 feed authorization module

This module uses the official Upstox Market Data Feed V3 authorization endpoint `GET https://api.upstox.com/v3/feed/market-data-feed/authorize` with a locally configured bearer token. It validates the returned `authorized_redirect_uri` against a strict Upstox-owned `wss://` host allowlist. Redirects from the HTTPS authorization endpoint are disabled. Response bodies are capped at 64 KiB. Credentials and signed WebSocket URLs are never exposed by the diagnostics API or written to logs.

## Local configuration

Set `MARKET_DATA_PROVIDER=UPSTOX`, `UPSTOX_ACCESS_TOKEN`, `MARKET_DATA_USAGE_RIGHTS_CONFIRMED=true` and `MARKET_DATA_ENTITLEMENT_CONFIRMED=true` only after checking account authorization and actual data-use rights. Keep secrets in an ignored local `.env` with restrictive permissions; never commit or paste them into chat.

`GET /api/v1/intelligence/providers/upstox/feed-authorization-readiness` performs configuration diagnostics only, with no outbound provider request.

## Important boundaries

The internal `authorize_feed` function is available for a future trusted background streaming worker. No public API returns the signed URI. This module **does not** establish a WebSocket connection, decode Protobuf, persist ticks, or display live prices. The live stream remains blocked until those pieces and tests are implemented. Upstox access tokens may expire and require user authorization; uninterrupted autonomous login cannot be promised.

Run `python -m unittest discover -s tests` from the `intelligence` directory.
