# Provider batch quality pipeline — on-demand, read-only

ATLAS now has a full **provider-review vertical** from React Market & Data Health through FastAPI, to the opt-in Upstox historical adapter, with unit and UI tests. This is a staging/quality-review feature, **not automatic ingestion**.

## Workflow

1. Confirm lawful data-use rights and account entitlements. Configure `MARKET_DATA_PROVIDER=UPSTOX`, `MARKET_DATA_USAGE_RIGHTS_CONFIRMED=true`, `MARKET_DATA_ENTITLEMENT_CONFIRMED=true`, `UPSTOX_ACCESS_TOKEN` and optionally `MARKET_DATA_RATE_PER_SECOND=1` in your local, ignored `.env`.
2. Recreate the intelligence container: `docker compose up -d --force-recreate intelligence`.
3. In **Market & Data Health → Provider batch review**, enter one to five distinct NSE/BSE equity instrument keys and a historical window.
4. Review each instrument's candle count, last trade date, age, adjustment uncertainty, missing exchange-session mapping and source-to-local-registry mapping.
5. Keep using the existing manually validated CSV ingestion pipeline for actual stored market data; this feature does not bridge the provider payload into it.

## API

`POST /api/v1/intelligence/providers/upstox/batch-review`

```json
{
  "instrument_keys": ["NSE_EQ|INE848E01016"],
  "from_date": "2026-11-01",
  "to_date": "2026-11-13",
  "max_age_days": 7
}
```

- At most 5 keys, 366 calendar days and 500 provider candles per key.
- Sequential on-demand requests with configurable per-request pacing (0 < rate <= 5 requests/s); no scheduler, queue, retries or persistent cache.
- Per-instrument provider failures are sanitized and do not conceal successful independent reviews.
- Results intentionally exclude raw candles and credentials; adjustment, session and local instrument mappings remain unverified.
- No research scoring, trade action, auto-import or full-market coverage. Calendar-day age is not a trading-session SLA.
- This endpoint is intended for **loopback-only personal use** and has no user authentication. Do not expose it on public networks.

## Verification

```sh
cd intelligence && python3 -m unittest discover -s tests -v
cd ../frontend/trading-dashboard && npm ci && npm test && npm run build
```

## Remaining blockers before automatic ingestion

Verified provider terms and API permissions; explicit instrument-to-local-registry mapping; exchange-session reconciliation; adjustment/corporate-action provenance; backend transaction/audit bridge; token lifecycle; durable rate-limit enforcement; source freshness SLAs and security review. This milestone does not claim those are complete.
