# Provider readiness and safe activation

ATLAS remains in manual CSV mode by default. The status endpoint is a **local diagnostic**, not an authentication test or market-data subscription check.

`GET http://127.0.0.1:8000/api/v1/intelligence/providers/status`

The response reports configured provider, whether credentials exist (never their value), usage-rights and entitlement declarations, and blockers. Its `status` is always `NOT_READY` and `automatic_collection_enabled` is always `false` until a licensed adapter is separately implemented, verified and approved.

## Environment declarations
- `MARKET_DATA_PROVIDER=MANUAL_CSV` (default), or `UPSTOX` for readiness diagnostics only.
- `UPSTOX_ACCESS_TOKEN`: optional secret, never returned by the diagnostic. Keep it out of source control.
- `MARKET_DATA_USAGE_RIGHTS_CONFIRMED=false`: operator declaration that the intended data use is contractually permitted.
- `MARKET_DATA_ENTITLEMENT_CONFIRMED=false`: operator declaration that the provider account has relevant data entitlements.
- `MARKET_DATA_AUTO_REFRESH=false`: remains disabled even if changed to true, until an adapter is verified.
- `MARKET_DATA_RATE_PER_SECOND=1`: configured safety ceiling; no requests are made by this feature.

Setting these declarations to true **does not** independently verify a contract, authenticate with the provider, start background refresh, or unlock live data. Obtain appropriate data rights and verify API entitlements before connecting a provider. Do not scrape protected exchange endpoints.

## Verification
From `intelligence`: `python3 -m unittest tests.test_provider_readiness -v`. CI also runs the full Python suite and validates Compose configuration.

## Limitations
This milestone does not implement Upstox requests, token renewal, instrument mapping, exchange calendars, backfill, provider-side rate-limit handling, or reconciliation with the validated CSV ingestion pipeline. Those require a separately reviewed integration and controlled test credentials. Portfolio data remains local and untouched.
