# Logical services and collection jobs

Services: instrument-master; market-feed-adapter; historical-backfill; exchange-report-ingestor;
institutional-flow; global-news; feature-engine; trap-engine; prediction-engine; risk-engine;
signal-ledger; alert-service; dashboard-api; model-ops.

Jobs:
- Import NSE/BSE instrument masters before market; version and diff each file.
- Consume licensed quote/depth stream continuously; heartbeat, reconnect with exponential backoff.
- Build 1m candles on close; derive 5m/15m bars; validate OHLC and volume.
- Repair historical gaps after session close and on feed-gap detection.
- Poll permitted exchange report catalogues; hash raw files and preserve revisions.
- Poll FII/DII publication windows; reconcile provisional/final revisions.
- Poll deal and short-selling disclosures; end-of-day reconciliation.
- Ingest global news continuously; canonicalize URLs, hash, cluster duplicates and resolve entities.
- Refresh macro calendars daily; confirm actual releases at event time.
- Evaluate model performance daily after data finalization.
- Train candidate models offline weekly; require approval and walk-forward validation before promotion.

Every job requires idempotency keys, retry/backoff, dead-letter handling, run logs, source watermarks and replay.
