# Opt-in local readiness monitoring

The ATLAS intelligence service can periodically observe the **existing local** NAV, institutional flow and news evidence databases. It writes the same deduplicated incident ledger as the manual "Record current readiness" action. It does not connect to an exchange, broker, AMFI, or newswire; it never enables automated data collection, investment recommendations or trading.

## Configuration
In the local `.env` file:
```env
ATLAS_READINESS_MONITOR_ENABLED=true
ATLAS_READINESS_MONITOR_INTERVAL_SECONDS=900
```
Run `docker compose up --build -d`. Monitoring defaults to **off**. Valid intervals are 60–86400 seconds. Invalid intervals fail closed (monitor disabled). One background asyncio task starts per intelligence process and runs its blocking local SQLite checks off the event loop. The task is cancelled on shutdown. Keep a **single intelligence process** to avoid duplicate observations; this implementation is not a distributed leader-elected scheduler.

## Endpoints and UI
- `GET /api/v1/intelligence/reliability/monitor`: enabled/running status, configured cadence, completed observations, last success and sanitized error code.
- `GET /api/v1/intelligence/reliability/incidents`: persistent open/resolved incident history.
- `POST /api/v1/intelligence/reliability/observe`: manual immediate local observation, retained.
- Market & Data Health → Data reliability incidents displays monitor status and incident history. Refresh the page to update the monitor status.

A recent local import is **not** evidence of a verified live feed. The `MARKET_DATA:UNVERIFIED_SOURCE` incident remains open while external provider authorization is absent. A scheduler success only means the local readiness snapshot was recorded.

## Tests
Run `cd intelligence && python -m unittest discover -s tests -p 'test_reliability_monitor.py'`. CI additionally runs the full Python suite, React build/tests, Spring Boot and Compose checks. Do not merge until all pass.

## Remaining work
An authenticated, entitled provider adapter and legally permitted automated source access remain separate blockers. Future production scaling requires leader election, process health metrics, and alert routing with explicit notification deduplication.
