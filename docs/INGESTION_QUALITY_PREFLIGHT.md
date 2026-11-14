# Candidate ingestion quality preflight

This module is an end-to-end **read-only validation lab** for provider-supplied or manually prepared observations. It does **not** fetch market data, persist prices, enable automated collection or execute trades. It is intended as a safe prerequisite to connecting an independently authorized market-data adapter.

## Local usage
1. Run `docker compose up --build -d` and open http://localhost:5173.
2. Open **Market & Data Health → Ingestion batch quality gate**.
3. Select dataset and mode; paste a JSON array with 1–250 observations, then click **Validate batch**.
4. Review row-specific duplicate, future timestamp and stale-data errors. Even a quality-passing batch remains **not authorized for ingestion** until an external provider and independent entitlements are verified.

Example **synthetic test data only**, not a real quote (replace the timestamp with a current timezone-aware time when testing):

```json
[
  {"instrument":"NSE:TEST","observed_at":"2026-11-14T01:59:00Z","value":"125.50","source_id":"TEST_SOURCE"}
]
```

## API
`POST /api/v1/intelligence/ingestion/quality-preflight` with JSON:
```json
{"dataset":"EQUITY_QUOTES","mode":"MANUAL_IMPORT","candidates":[{"instrument":"NSE:TEST","observed_at":"2026-11-14T01:59:00Z","value":"125.50","source_id":"TEST_SOURCE"}]}
```

Supported datasets: `EQUITY_QUOTES`, `EQUITY_DAILY`, `MF_NAV`. Freshness limits: 120 seconds, 48 hours and 7 calendar days respectively. These are **preflight validation defaults**, not guaranteed market availability or provider SLAs. Observations more than 30 seconds in the future fail. Duplicate key: source, instrument and UTC observation time. Values must be positive, finite and no greater than 1 billion. Timestamps must carry a timezone. Pydantic rejects unknown fields and over-limit batches.

The response always includes `authorized_to_ingest: false`, `stored_records: 0` and `live_market_data_connected: false`. Entitlement manifests are only local declarations and are **never** accepted as independent verification. No data are written to the database.

## Tests
Run `cd intelligence && python3 -m unittest discover -s tests -p 'test_ingestion_quality.py'`, then all Python tests and the React build/test suite. CI is required before merging.

## Security and future integration
This is a local-only API; no authentication is implemented. Keep Docker ports bound to loopback. Do not paste credentials, private contracts or personal information. Before connecting any automatic provider, implement independently verified dataset/usage entitlements, provider authentication, bounded retries and rate limits, quote integrity checks, durable provenance, incident handling and end-to-end integration tests. The existing Upstox approval remains pending.
