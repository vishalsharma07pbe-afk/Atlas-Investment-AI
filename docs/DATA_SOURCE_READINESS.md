# ATLAS Data Source Readiness Gates

## Purpose
ATLAS now has a read-only, fail-closed operational overview of three existing persisted datasets: mutual fund NAV, institutional flows and global news. It separates **presence**, **age**, **verification** and **authorization** rather than treating imported records as a live feed.

## Implementation
- API: `GET /api/v1/intelligence/data-readiness` (intelligence service); frontend proxy path `/intelligence/api/v1/intelligence/data-readiness`.
- UI: **Market & Data Health → Data source readiness**; refresh button and visible service errors.
- Storage: reads existing SQLite files in read-only mode; no new volume or migration. Missing files are not created by this endpoint.
- Freshness policy: NAV 5 calendar days, institutional flows 3 calendar days, news 72 hours. These are conservative **display heuristics**, not exchange trading-calendar or contractual SLA calculations.
- Statuses: `NOT_IMPORTED`, `RECENT_LOCAL_EVIDENCE`, `STALE_DATA`, `FUTURE_TIMESTAMP`, `INVALID_TIMESTAMP`, `STORAGE_UNAVAILABLE`.
- All manual evidence remains unverified and non-live. A recent observation never authorizes a trading recommendation.
- No automated market collection, news scraping, account authorization or trading is introduced.

## Verification
Run `cd intelligence && python -m unittest discover -s tests -p 'test_data_readiness.py'` and the repository's complete GitHub Actions suite. Verify missing databases, stale and future records, corrupted SQLite, API response, React build and UI loading/error states.

## Activation requirements
1. Obtain source-specific permissions and entitlements for automated collection.
2. Implement and test the licensed provider adapter, authentication, rate limits and reconnect behavior.
3. Add actual source heartbeat and provider-acknowledged timestamps; this endpoint currently measures only persisted local evidence.
4. Establish exchange calendars, per-provider freshness SLAs and data reconciliation before enabling actionable research.

Never treat `RECENT_LOCAL_EVIDENCE` as proof of a connected provider.
