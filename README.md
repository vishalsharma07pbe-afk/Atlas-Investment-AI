# ATLAS — Private Investment Intelligence (Local Alpha)

**P0 verification:** See [docs/P0_VERIFICATION_RUNBOOK.md](docs/P0_VERIFICATION_RUNBOOK.md) for JWT login, Upstox vault setup, NSE/BSE search, AMFI NAV, AI committee, freshness checks and local smoke-test gates. The original alpha instructions below describe earlier milestones; do not assume they reflect the latest authenticated API.

**P2 Research Lab:** See [docs/P2_IMPLEMENTATION_STATUS.md](docs/P2_IMPLEMENTATION_STATUS.md) for grounded AI research, leakage-controlled walk-forward evaluation, multi-factor screening, and assumption-driven personal planning.

A local-first investment research dashboard. This is a **functional portfolio alpha**, not a complete live trading intelligence system. It does not produce stock tips without verified feeds.

The market-data foundation now supports a validated NSE/BSE instrument registry and strict manual CSV ingestion of daily OHLCV data. See [docs/M1_DATA_INGESTION.md](docs/M1_DATA_INGESTION.md) for source/legal boundaries, templates, validation, migrations and security.

Milestone 2 adds provider-independent daily technical analysis, explainable patterns, a Stock Explorer, and the refined Liquid Glass dashboard while retaining a truthful empty state until licensed records are imported. See [docs/M2_MARKET_DATA_AND_CHART_INTELLIGENCE.md](docs/M2_MARKET_DATA_AND_CHART_INTELLIGENCE.md) for actual production counts, provider blockers, APIs, tests, builds, and visual verification.

## Start on Windows
1. Install Docker Desktop with WSL2 enabled and start Docker Desktop.
2. Extract the project. In PowerShell in the project directory run `Copy-Item .env.example .env`.
3. Run `docker compose up --build -d`.
4. Open http://localhost:5173 in your browser.
5. To stop: `docker compose down` (preserves your database volume).

If upgrading an existing installation, apply `infrastructure/postgres/init/002_portfolio.sql` to the existing database **once** using:
`docker compose exec -T postgres psql -U trading -d trading < infrastructure/postgres/init/002_portfolio.sql` (PowerShell input redirection may not work; use `Get-Content infrastructure/postgres/init/002_portfolio.sql | docker compose exec -T postgres psql -U trading -d trading` instead). New installations automatically run both SQL init files.

## Portfolio
Use the My Portfolio tab to add holdings manually or import a simple CSV with columns `symbol,asset_type,quantity,average_cost,last_price`. `asset_type` must be `EQUITY` or `MUTUAL_FUND`. `last_price` is optional. Prices are **manually entered**, not live. CSV imports upsert positions by symbol and asset type, and do not track transaction history. Do not import an untrusted CSV. The parser is intentionally basic and does not handle quoted commas. The empty `sample-holdings.csv` shows the header.

### API
- `GET /api/v1/portfolio/holdings`
- `POST /api/v1/portfolio/holdings` JSON `{ "symbol":"ABC", "assetType":"EQUITY", "quantity":10, "averageCost":100, "lastPrice":110 }`
- `DELETE /api/v1/portfolio/holdings/{id}`
- `GET /api/v1/portfolio/analysis`
- `GET /api/v1/health`

## Security and limits
Only run on your trusted local computer. Docker services are bound to `127.0.0.1` by default. There is **no login authentication yet**, so do not expose ports, reverse-proxy it to the internet, or use on a shared computer. Portfolio holdings are stored in a local Docker-managed PostgreSQL volume, **not encrypted at rest** in this alpha. Set a strong database password in `.env`. Back up the volume before upgrades. There is no broker connection, no live market provider, no external AI API, and no trade execution. Market and recommendation tabs are intentionally inactive until validated inputs exist. Basic concentration flags are not investment advice.
