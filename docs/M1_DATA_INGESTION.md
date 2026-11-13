# M1: NSE/BSE registry and daily OHLCV foundation

## Provider and legal boundary

ATLAS is in `MANUAL_CSV_ONLY` provider mode. No exchange website or protected endpoint is scraped. NSE's current data policy and EOD product pages describe agreement/subscription requirements, and a comparable BSE automated-use right was not verified during implementation. Consequently, the application accepts only local files for which the operator has the right to import and retain the data.

The templates are in `data/templates/`. The strict adapter accepts UTF-8, comma-separated, unquoted fields only (no embedded commas), a maximum of 10 MB, and exact headers. Import in this order:

1. `POST /api/v1/data-import/instruments`
2. `POST /api/v1/data-import/market-sessions`
3. `POST /api/v1/data-import/corporate-actions` when applicable
4. `POST /api/v1/data-import/daily-candles`

Example:

```sh
curl -F file=@data/templates/instruments.csv http://127.0.0.1:8080/api/v1/data-import/instruments
```

The dashboard offers the same four imports under **Market & Data Health**.

## Validation and storage behavior

- Registry rows require `NSE` or `BSE`, a unique exchange/symbol/series mapping, optional checksum-valid ISIN, listing status, and source revision.
- Session rows require an ISO-8601 timestamp with offset. Trading-day timestamps must match the stated date in `Asia/Kolkata`, and close must follow open.
- Candle rows require a known instrument and one validated `REGULAR` trading session for the date.
- Prices must be positive; high/low must contain open and close; volume must be a nonnegative integer.
- Duplicate keys inside a file reject the entire file. A byte-identical successful artifact is reported as `DUPLICATE` and is not written again.
- Changed canonical candles become revisions and emit `CANDLE_REVISION`. More than 25% close-to-close movement emits `SUSPICIOUS_PRICE_DISCONTINUITY`, or `CORPORATE_ACTION_CONTEXT` when an action exists on the date.
- A latest date older than ten calendar days emits `STALE_SOURCE`.
- `adjustment_status` is mandatory and must be `RAW_UNADJUSTED` or `ADJUSTED`. ATLAS never treats raw prices as adjusted. Corporate actions are contextual records; this milestone does not calculate an adjusted price series.
- Every attempt creates an ingestion run. Failed files create `FILE_REJECTED`; accepted writes and revisions are transactional.

## Migrations and existing installations

Flyway baselines an existing Docker-init installation at version 2 and applies the additive `V3__instrument_registry_and_eod_ingestion.sql`. It does not drop or rewrite portfolio tables. New installations receive `001_init.sql` and `002_portfolio.sql` from PostgreSQL initialization; the backend then establishes the version-2 baseline and applies version 3.

Before the first migration of the inspected installation, a compressed backup was saved as `backups/atlas_pre_m1_20261113.dump`. Do not delete the `pgdata` volume when upgrading.

## Local security

- All published ports bind to `127.0.0.1`.
- `.env` and backups are ignored; `.env` is mode `0600` on the inspected installation.
- Compose refuses to start PostgreSQL or the backend when `POSTGRES_PASSWORD` is absent.
- For an installation still using a known/default password, run `scripts/rotate-local-db-password.sh`. It first creates a compressed backup, changes the database role password, updates `.env` atomically with mode `0600`, and prints the required restart command. Do not commit the generated secret.

## Verification commands

```sh
npm --prefix frontend/trading-dashboard run build
docker compose build backend frontend
docker compose up -d backend frontend
docker compose exec -T postgres psql -U trading -d trading -c "select count(*) from instruments; select count(*) from market_candles where timeframe='1d';"
curl http://127.0.0.1:8080/api/v1/data-health/summary
```

Integration tests use an isolated PostgreSQL schema and cover the migration baseline, registry/session loading, OHLCV validation, idempotency, rejection/audit reporting, discontinuity detection, and Data Health API.
