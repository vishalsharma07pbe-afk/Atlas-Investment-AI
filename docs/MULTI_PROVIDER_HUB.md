# Multi-provider research hub — initial safe slice

This is a **read-only** integration of the existing durable manually imported AMFI NAV catalog with a normalized provider registry and search API. It does **not** claim a free real-time NSE/BSE feed or silently scrape exchange websites.

## Routes
- `GET /api/v1/intelligence/data-hub/sources` — provider capabilities, authorization states and no-live-data disclaimer.
- `GET /api/v1/intelligence/data-hub/search?asset_type=MUTUAL_FUND&query=Example` — local validated NAV observations with date, source and stale/EOD status.
- `asset_type=EQUITY` — explicit unavailable response until an authorized provider adapter and ingestion pipeline are verified.

The React **Market & Data Health** tab exposes provider status and research search. The module does not request remote data or enable auto-refresh. Local NAV snapshots are stale when older than four calendar days; weekends/holidays may require a trading-calendar-aware refinement. Source dates are not intraday timestamps.

## Activation blockers
Upstox approval, independent proof of data rights, provider-specific rate limits and exchange redistribution terms. Additional providers are **placeholders only** and are never automatically called. Future provider adapters must include licensed endpoint configuration, schema normalization, bounded retry/backoff, rate limits, circuit breaker, persistent observation provenance and freshness checks before automatic failover.

## Tests
`cd intelligence && python -m unittest discover -s tests`
React: `cd frontend/trading-dashboard && npm run build`.
No order placement or brokerage account access is required for the local NAV view.
