# Upstox V3 daily historical preview (opt-in)

This milestone adds a **read-only, single-request historical preview**, not a live market feed, automatic collection, or ingestion pipeline. ATLAS remains manual-CSV-first.

Upstox documents the V3 daily historical endpoint at https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/ . The adapter uses only `GET https://api.upstox.com/v3/historical-candle/{instrument_key}/days/1/{to_date}/{from_date}`.

## Enable for a permitted account
1. Confirm your provider contract and data entitlement cover the intended use and retention. Do not assume account access automatically grants all redistribution or storage rights.
2. Set `MARKET_DATA_PROVIDER=UPSTOX`, `MARKET_DATA_USAGE_RIGHTS_CONFIRMED=true`, `MARKET_DATA_ENTITLEMENT_CONFIRMED=true`, and `UPSTOX_ACCESS_TOKEN` in your local ignored `.env`. These are self-declarations, not independently verified licenses.
3. Restart intelligence: `docker compose up -d --force-recreate intelligence`.
4. For an instrument key that belongs to NSE/BSE cash equity, request a past window of at most 366 days:

```sh
curl --get 'http://127.0.0.1:8000/api/v1/intelligence/providers/upstox/daily-preview' \
  --data-urlencode 'instrument_key=NSE_EQ|INE848E01016' \
  --data-urlencode 'from_date=2026-01-01' \
  --data-urlencode 'to_date=2026-01-31'
```

The result is capped at 500 candles and 2 MB of provider response. Each row is tagged `adjustment_status=UNVERIFIED`, so it **must not** be passed directly into research signals or backtesting. The adapter rejects malformed candles, duplicates, invalid dates and unexpected redirects; provider HTTP errors are sanitized. Credentials are never returned.

## Still missing
No automatic refresh, rate-limit queue, retries, token renewal, provider-to-registry mapping, corporate-action adjustment verification, ingestion audit, exchange session reconciliation, historical gap fill or provider-specific live freshness SLA. No data is stored by this preview. The provider-readiness diagnostic intentionally remains `NOT_READY` for automated collection. Never expose this unauthenticated local endpoint to the internet.
