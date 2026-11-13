# Market data readiness gate

This read-only, on-demand review evaluates the Spring Boot `/api/v1/data-health/summary` response before allowing research signals to be considered eligible for *further* checks.

## API
`GET /api/v1/intelligence/market/readiness` with optional bounded query arguments `max_calendar_age_days` (0–30), `minimum_instruments`, `minimum_candles`, and `require_live_feed` (default true). It reads only the internal backend health summary, makes no provider requests and persists nothing.

A response is `BLOCKED` if there is no verified live feed (default policy), insufficient coverage, unresolved or unknown quality events, missing source provenance or dated evidence, future source dates, or stale source evidence. Unknown values never pass. `READY` is **not** proof of provider licensing, live price accuracy, model validity, or suitability for trading; it merely passes this preliminary gate. Other research gates must still apply. No order execution is enabled.

The Data Sources dashboard includes an explicit `Check market readiness` action. Until clicked, no request is made. Failure to contact the backend is shown as an error, never a ready status.

Tests: `python -m unittest intelligence.tests.test_market_readiness` and `npm test` in `frontend/trading-dashboard`.
