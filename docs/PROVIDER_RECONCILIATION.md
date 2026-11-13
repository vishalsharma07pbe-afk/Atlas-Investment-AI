# Provider-to-registry reconciliation gate

ATLAS adds an end-to-end **read-only reconciliation review** spanning Python validation, FastAPI, the Market & Data Health dashboard and tests. This does **not** yet implement a validated provider-to-database ingestion bridge.

## Endpoint

`POST /api/v1/intelligence/providers/reconcile`

Payload fields:
- `mapping`: `instrument_key`, `exchange`, `symbol`, `series`, `isin`, and explicit boolean declarations `adjustment_verified`, `sessions_verified`, `usage_rights_verified`.
- `registry_exchange`, `registry_symbol`, `registry_series`, `registry_isin`: independently supplied local-registry identifiers.
- `candles`: 1–500 records with `trade_date`, OHLC, volume, `adjustment_status`.
- `known_session_dates`: dates independently checked against the relevant exchange's trading calendar.
- `provider_source_revision`: user-supplied provenance reference.

The review flags exchange-key and registry mismatches, duplicate/unsorted/future candle dates, invalid OHLCV, missing session dates, mixed or unverified adjustments, and absent rights declarations. It intentionally **always** requires independent provenance audit: user-provided declarations are not a proof of rights, exchange session status or corporate-action adjustments. It never creates an import-ready CSV or writes to the database.

## Why ingestion is blocked

The existing backend daily-candle importer requires registered instruments, regular market sessions, source revisions and explicit `RAW_UNADJUSTED` or `ADJUSTED` status. Upstox historical previews do not establish these properties independently. Marking them verified without evidence would contaminate backtests and recommendations. Until a backend audit bridge and verified mappings exist, use only lawfully sourced CSV files through the existing validated importer.

## Tests

`cd intelligence && python3 -m unittest discover -s tests -v`

`cd frontend/trading-dashboard && npm test && npm run build`

No background polling, automatic trading or provider credential exposure is added. This panel is intended for loopback-only personal use and should not be exposed publicly without authentication.
