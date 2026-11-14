# P0 ingestion reliability: durable job state foundation

Implements a local SQLite ledger for explicitly submitted import jobs. The ledger enforces idempotency keys, bounded retries with exponential backoff, non-sensitive error codes, and a maximum of five attempts. The state transitions are PENDING -> RUNNING -> SUCCEEDED or RETRY -> FAILED.

**This module is not a scheduler or importer.** It does not fetch Upstox/AMFI, execute jobs, store tokens, infer provider rights or make trading decisions. No background worker is enabled. Authorization checks must be added to the executor before it is connected to any external source.

Use the module functions `enqueue`, `claim`, `finish`, and `status` from an authorized future ingestion worker. Data persists in `ATLAS_INGESTION_DB_PATH`; Docker volume configuration is included. Never include tokens in source references or error codes.
