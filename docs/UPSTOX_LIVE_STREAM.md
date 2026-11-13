# Upstox V3 real-time market feed — implementation status

Provider selected: **Upstox**, using its documented free market-data API, subject to an authorized account and data-use rights.

## Implemented in this PR
- WSS redirect allowlist for Upstox-owned hosts; signed URL never logged
- Strict LTPC subscription construction with bounded key count
- Tick normalization and freshness/future-time rejection
- Fail-closed stream readiness model
- Unit tests for security, subscriptions, stale data and readiness

## Not yet implemented — do not claim live prices
- Local user OAuth setup and safe access-token renewal
- V3 authorization request and WebSocket connection/reconnection
- Official V3 Protobuf schema compilation and binary decoding
- Validated tick persistence/cache, backend stream API and dashboard subscriptions
- Exchange-session-aware freshness and operational soak testing

The official V3 feed sends binary Protobuf, not JSON; do not pass undecoded bytes to `normalize_tick`. The authorized WSS redirect URI is a secret-bearing single-use URL. Avoid exposing it in browser logs or API responses. No trading/order endpoints should be connected.

Upstox documentation: https://upstox.com/developer/api-documentation/v3/get-market-data-feed/
