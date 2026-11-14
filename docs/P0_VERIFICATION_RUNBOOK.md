# P0 local verification runbook
## Preconditions
Install Docker Desktop, Node.js and Java 21. Work only on localhost. Use legally authorized Upstox read-only API credentials. Do not commit access tokens or the vault key.
1. Copy `.env.example` to `.env`. Configure `SPRING_DATASOURCE_PASSWORD`, `ATLAS_JWT_SECRET` (base64 of at least 32 random bytes), `ATLAS_VAULT_MASTER_KEY` (a valid 32-byte base64 AES key), `ALLOW_REGISTRATION=true` for first-time setup, and the other required compose environment variables. Restrict access to this file.
2. Start services: `docker compose up --build -d`. Inspect `docker compose ps` and backend logs. Confirm PostgreSQL Flyway migrations V3–V12 applied successfully.
3. Open `http://localhost:5173`. Register with a unique email and a password of at least 12 characters; sign in. Check `GET /api/v1/auth/me` returns your user.
4. Enter the Upstox access token and its actual expiry in the vault card. The token must be obtained via Upstox's authorized authentication flow. The application does not generate or renew tokens automatically. Do not share tokens in screenshots or logs.
5. In the authenticated workspace, sync Upstox holdings. Confirm `POST /api/v1/portfolio/sync/upstox` returns a count. Check a second account cannot access the first account's holdings.
6. Allow the instrument master refresh scheduler (set `atlas.market.feeds.enabled=true` in backend configuration) to run, or trigger the service through an authorized admin workflow. Search an NSE/BSE equity and confirm an Upstox instrument key and ISIN are present. Search mutual funds after the AMFI NAV refresh.
7. Confirm daily and intraday OHLCV imports are idempotent, provenance is UPSTOX and `instrument_source_freshness` updates. Check `GET /api/v1/system/freshness`; verify unresolved equity alerts and AMFI scheme alerts are clearly displayed. The AMFI expected date advances only after 22:00 IST on a published trading session.
8. Select AI Committee, check provider health and analyze a valid stock symbol. If the intelligence service is disabled or unreachable, report the unavailability instead of presenting an invented recommendation.
9. Test the local build: `cd frontend/trading-dashboard && npm ci && npm run build && npm test`. Test backend: `cd backend/trading-core && mvn test`. Run the intelligence tests according to its own service README. Review all GitHub Actions checks before merging.
10. Stop: `docker compose down`. Never use `down -v` unless deliberately deleting the database. Disable `ALLOW_REGISTRATION` after creating the account.
## P0 acceptance gates
- P0-1: authorized Upstox instrument mapping, live quote, 1D/1m/15m candle ingestion, deduplication and provenance
- P0-2: AMFI NAV refresh, scheme search, historical NAV and performance, schedule-aware freshness
- P0-3: NSE/BSE calendar, retry ledger and deduplicated alerts
- P0-4: JWT authentication, owner-scoped holdings and AES-GCM credential vault
- P0-5: UI login/logout, searches, AI report, freshness warnings, backend/frontend/intelligence CI and local smoke test
## Limitations
Live market data requires an authorized, unexpired Upstox token. AMFI NAV is end-of-day, not a real-time price. Automated tests cannot substitute for a local live-credential smoke test. Do not claim a live run without completing step 4–8.
