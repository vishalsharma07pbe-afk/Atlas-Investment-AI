# P0: authorized read-only multi-provider quote adapters

This module adds two optional HTTPS quote sources to the existing validated, ordered failover router:

- Upstox V3 full market quote endpoint for explicitly mapped instrument keys. Configure `UPSTOX_ACCESS_TOKEN`, `ATLAS_UPSTOX_SYMBOL_MAP` (JSON exact symbol-to-key mapping), and `ATLAS_UPSTOX_QUOTES_AUTHORIZED=true` only after independently verifying quote entitlement and terms.
- Polygon/Massive last-trade endpoint for supported **US** symbols. Configure `ATLAS_POLYGON_API_KEY` and `ATLAS_POLYGON_QUOTES_AUTHORIZED=true` only after verifying entitlement, geographic coverage and personal-use terms.

GET `/api/v1/intelligence/data-hub/quotes/{symbol}?max_age_seconds=60` returns a validated quote, source and attempts, or no quote. GET `/api/v1/intelligence/data-hub/provider-adapters` returns configuration state without secrets. Only a provider explicitly mapped to the requested market identity can be tried. A symbol configured for both Indian and US markets is ambiguous and blocked before any network request. Invalid, stale, future-dated, wrong-instrument or missing-timestamp quotes fail closed. The default configuration makes **no external calls**.

**Important limitations:** This is an on-demand quote adapter, not instrument discovery, historical OHLCV, NAV automation, a streaming feed or evidence of active provider entitlement. A valid HTTP response does not independently establish data-use rights. Upstox NSE/BSE and Polygon US instruments are not interchangeable; use Polygon only for appropriate US symbols. No trade execution. The user must verify actual provider response schemas and terms with authorized credentials before declaring production readiness. Never commit tokens or expose the service to the internet without authentication.

## Recovery and provider boundaries

The optional HTTP quote router shares circuit state across requests in one process. A 401/403 opens a 15-minute cooldown and a 429 opens a 60-second cooldown; other failures retain the bounded circuit policy. The supervised Upstox WebSocket stops on explicit credential rejection and uses a 15-minute restart cooldown; other exhausted reconnect attempts use 60 seconds. Configuration inspection remains read-only. Settings feed health shows the recovery status and prompts the operator to renew rejected credentials locally. Restart the affected services after replacing a token. No automatic broker login or credential renewal is attempted. Circuits reset when the process restarts.

Polygon covers explicitly configured US symbols only; it is not an Indian-equity fallback. Same-market Indian backup sources require separately approved rights, exact instrument identity mappings and verified adapters. These changes do not claim such a backup exists or cover all direct HTTP ingestion paths. Market calendars, corporate actions, expanded universe and real-provider acceptance remain separate work.
