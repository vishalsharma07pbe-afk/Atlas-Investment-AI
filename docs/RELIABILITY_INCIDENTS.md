# Local reliability incident history

The Data Health workspace includes a persistent reliability incident timeline. Clicking **Record current readiness** evaluates the existing read-only dataset readiness service and records a complete snapshot. Missing, stale, future-dated, invalid-timestamp and inaccessible datasets become incidents; an unverified market-data source is always flagged. No market-data fetch or trade is performed.

## Endpoints
- `GET /api/v1/intelligence/reliability/incidents?limit=50`: read persisted history (1–100).
- `POST /api/v1/intelligence/reliability/observe`: server-computed snapshot, no user-provided issue assertions.

The backend maps readiness status to a bounded set of incident codes, deduplicates by dataset and code, increments observation count, and marks absent incidents resolved. Resolution only means the problem disappeared from the latest local snapshot; it does not imply verified licensing, live connectivity or trading readiness. A new occurrence reopens a resolved issue. A Docker volume persists records through restarts.

## Local verification
`cd intelligence && python3 -m unittest discover -s tests -p 'test_reliability_incidents.py'`

Then run the full Python suite, React build/tests, Spring Boot and Compose CI. Start with `docker compose up --build -d`; open **Market & Data Health**, record readiness, confirm the timeline, restart containers and confirm persistence. Do not expose the unauthenticated local API publicly.

## Known limits
Observations are **on-demand**, not scheduled monitoring. No licensed live feed is connected; this module does not authorize ingestion. Automatic polling and alert delivery require a separate, explicitly scoped module with proper rate limiting, entitlement verification and recovery behavior.
