# Provider failover engine — safe offline integration

The read-only `provider_router.py` implements ordered primary/backup routing, entitlement gating, strict quote symbol and asset-type matching, positive finite price validation, timezone-aware observation timestamps, configurable freshness, and per-provider circuit breaking. Exceptions are deliberately not returned to clients because they could contain secrets.

**No production remote adapter is connected.** The engine is independently testable using injected adapters. It cannot place trades. The readiness API is truthful about lack of live feeds.

## Endpoint
`GET /api/v1/intelligence/data-hub/failover-readiness`

Returns `SAFE_OFFLINE`, implemented router capabilities, configured adapter count (zero), and licensing blockers. The Market & Data Health screen displays this information.

## Before enabling a remote adapter
1. Obtain and verify NSE/BSE data use permissions and provider terms for automated personal research and storage.
2. Validate credentials, exchange instrument identifiers, permitted quote rate and subscription expiry.
3. Implement provider-specific read-only HTTP transport with timeout, backoff and concurrency bounds; never log tokens.
4. Persist validated observations with source, original timestamp, ingestion timestamp and entitlement metadata.
5. Add integration tests for outage, 429, stale quote, mismatched instrument, circuit recovery, and backup licensing.
6. Only then wire authorized adapters into the router and separately enable automatic failover.

## Tests
`cd intelligence && python -m unittest discover -s tests`
`cd frontend/trading-dashboard && npm run build`

The Java shared operator Upstox daily, benchmark and intraday collectors now use one persistent PostgreSQL cooldown before new work. Numeric Retry-After, bounded exponential delays and fixed sanitized failure codes protect repeated requests. Personal owner vault operations, unauthenticated public feeds and Python transports are intentionally isolated; independent same-market provider redundancy remains unverified. The existing data-health summary exposes the operator cooldown, which is not a live-feed or entitlement certificate.

Public Upstox master and AMFI NAV scheduling now uses independent persisted per-provider claims in PostgreSQL, existing audit records, retry cooldowns and recovery of expired claims. The source-readiness UI distinguishes these job states from source freshness and live connectivity. This is not independent same-market failover or exactly-once external execution.
