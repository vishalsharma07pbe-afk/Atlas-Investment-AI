# P0: authorized read-only multi-provider quote adapters

This module adds two optional HTTPS quote sources to the existing validated, ordered failover router:

- Upstox v2 full market quote endpoint for explicitly mapped instrument keys. Configure `UPSTOX_ACCESS_TOKEN`, `ATLAS_UPSTOX_SYMBOL_MAP` (JSON exact symbol-to-key mapping), and `ATLAS_UPSTOX_QUOTES_AUTHORIZED=true` only after independently verifying quote entitlement and terms.
- Polygon/Massive last-trade endpoint for supported **US** symbols. Configure `ATLAS_POLYGON_API_KEY` and `ATLAS_POLYGON_QUOTES_AUTHORIZED=true` only after verifying entitlement, geographic coverage and personal-use terms.

GET `/api/v1/intelligence/data-hub/quotes/{symbol}?max_age_seconds=60` returns a validated quote, source and attempts, or no quote. GET `/api/v1/intelligence/data-hub/provider-adapters` returns configuration state without secrets. Providers are tried in order. Invalid, stale, future-dated, wrong-instrument or missing-timestamp quotes fail closed. The default configuration makes **no external calls**.

**Important limitations:** This is an on-demand quote adapter, not instrument discovery, historical OHLCV, NAV automation, a streaming feed or evidence of active provider entitlement. A valid HTTP response does not independently establish data-use rights. Upstox NSE/BSE and Polygon US instruments are not interchangeable; use Polygon only for appropriate US symbols. No trade execution. The user must verify actual provider response schemas and terms with authorized credentials before declaring production readiness. Never commit tokens or expose the service to the internet without authentication.
