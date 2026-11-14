# P0 provider-neutral historical OHLCV store

Daily candles can be imported programmatically with `app.ohlcv_store.import_candles(symbol, market, source, rows)` from a future **authorized** ingestion worker. Each observation stores market, source, trading date, prices, volume and import time. Duplicate identical records are idempotent; conflicting records from the same source/date fail closed. Different sources remain separate and are never silently blended.

GET `/api/v1/intelligence/data-hub/ohlcv/{market}/{symbol}?limit=365` returns dated candles with source and age. Importing is **not exposed as an unauthenticated HTTP endpoint**. The existing ingestion ledger and persistent volume are reused. No automatic historical provider fetch, corporate-action adjustment, market-calendar reconciliation or verified feed is claimed. These require separate authorization and integration.
