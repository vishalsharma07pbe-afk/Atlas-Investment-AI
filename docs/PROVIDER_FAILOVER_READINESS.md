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

## Local Upstox HTTP transport finding (2026-11-26)
On the operator Mac and Docker, Python default/Accept-only requests to the public holiday endpoint returned 403; explicit truthful User-Agent ATLAS/2.0 returned 200 inside Docker, and curl HTTP/1.1 returned 200 on the Mac. Standardize the existing Java Upstox public master and REST requests, Python V3 historical and quote reads, authorization and WebSocket handshake identity to ATLAS/2.0. Existing authorization, TLS, signed URI, retry, entitlement and evidence gates remain in place. Other providers retain their existing request identity. Do not interpret this public endpoint test as successful authenticated history or streaming. Denied requests must remain denied. The registry refresh's generic validation/storage failure remains separately unconfirmed. No calendar dates were inferred or inserted. Verify corrected authenticated history, feed authorization and dated session responses locally before calendar synchronization; missing stored exchange sessions currently prevent equity discovery attempts.

## Registry reconciliation and classified import failures
Local diagnostics showed 9,927 NSE and 13,069 BSE raw mappings, 2,784 exact active NSE cash-equity joins and zero BSE joins; NSE discovery wrote 2,657 candles in 13 successful attempts. Upstox public master job had failed five times with the generic validation/storage code. Raw registry presence alone is not usable coverage. The existing master check now also requires at least one exact active cash-equity join per venue, and data health exposes raw mappings, active equities and exact mapped equities separately. Persisted public job errors now identify the fixed venue and import stage (invalid JSON/envelope, duplicate key, no validated equities, registry/mapping storage error, identity conflict). HTTP and backoff handling, transaction rollback and exact identity checks remain unchanged. No blanket conversion of legacy BSE mappings to equities. Actual provider payload and storage rejection reason remain to be verified locally. No assertion that BSE collection is fixed by diagnostics alone.

## Exhausted public catalog job recovery
After five failures the persistent schedule records FAILED with a one-hour (or longer provider-directed) deadline. The retry poll now includes FAILED when its deadline has elapsed; exhausted attempts remain capped at five until a successful run, keeping subsequent failed probes on the slow cadence. IDLE/SUCCESS jobs remain excluded from retry-only claims; lease, deadline, provider isolation, Retry-After and transaction safeguards are unchanged. A successful claim clears the error and the next normal refresh starts a new attempt sequence. This fixes the observed overdue Upstox retry after local deployment, not the still-unverified underlying registry import rejection.
