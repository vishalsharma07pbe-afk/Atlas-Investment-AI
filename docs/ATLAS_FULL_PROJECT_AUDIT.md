# ATLAS Full Project Audit and Implementation Readiness

**Audit date:** 13 November 2026 (Asia/Kolkata)  
**Scope:** repository inspection, read-only runtime/API checks, read-only PostgreSQL metadata and aggregate row checks, and external provider documentation review  
**Constraint observed:** no application source, configuration, database record, schema, migration, package, environment variable, Docker volume, or container was changed. This report is the only audit deliverable.

## Status legend

| Status | Meaning |
|---|---|
| **IMPLEMENTED** | Code exists, is connected to its runtime path, and was verified by inspection; where stated, a live read-only check also passed. |
| **PARTIAL** | A bounded subset works, but the product objective is not met or important correctness/operational work remains. |
| **PLACEHOLDER** | UI, schema, endpoint, or documentation exists mainly as a scaffold and has no real analytical/data pipeline behind it. |
| **MISSING** | No implementation was found. |
| **UNVERIFIED** | Present or claimed, but this audit could not establish correctness, licensing, runtime behavior, or production suitability. |

## 1. Executive summary

ATLAS is a coherent **local research alpha**, not yet an autonomous investment-intelligence system. Its strongest implemented vertical is manual portfolio storage: a React page writes holdings through Spring JDBC to PostgreSQL and displays cost, manually entered valuation, unrealized P&L, and two basic concentration warnings. The Python service provides a carefully worded evidence-intake prototype, a simple six-boolean trap heuristic, recommendation blocking, and read-only portfolio aggregation. All five Docker services were running during the audit; the frontend, Spring health endpoint, and FastAPI health/capabilities endpoints returned successfully.

The repository does **not** contain a market-data adapter, instrument importer, candle builder, fundamental parser, news pipeline, feature engine, charting implementation, backtester, calibrated prediction model, recommendation engine, or frontend connection to the intelligence service. Of the seven visible tabs, only **My Portfolio** performs useful work; the other six are intentionally styled placeholders. Redis is running but unused. Most of the 27 database tables are forward-looking schema with zero application writers or readers.

The safety posture is directionally correct: services bind to loopback, the intelligence service hard-blocks recommendations, no broker/order code exists, and documentation repeatedly distinguishes evidence coverage from confidence. However, security is alpha-grade. There is no authentication or authorization, the checked `.env` uses the documented default database password, its filesystem mode is `0644`, no `.gitignore` exists, API services have no origin policy/rate limiting, database storage is not encrypted, and mutable container tags are used. No credentials were copied into this report.

The immediate milestone should be **M1: a versioned instrument registry plus validated daily EOD candles with provenance and quality gates**. This should use the existing `exchanges`, `issuers`, `instruments`, `data_sources`, `ingestion_runs`, `data_quality_events`, `market_sessions`, `corporate_actions`, and `market_candles` tables. It should not add a second instrument or candle table. One schema correction is necessary: ISIN identifies a security, not an issuer; the current `issuers.isin` placement cannot represent multiple securities from one issuer correctly.

## 2. Audit method and verified runtime state

### Repository inspected

The relevant repository is small enough for complete source inspection. It contains:

- `frontend/trading-dashboard`: one React entry component, one stylesheet, Vite configuration, and Dockerfile.
- `backend/trading-core`: three Spring REST controllers, JDBC configuration, and Dockerfile.
- `intelligence`: one FastAPI module, three pinned Python dependencies, and Dockerfile.
- `infrastructure/postgres/init`: one foundation schema and one portfolio schema script.
- `docs/architecture`: algorithms/safeguards, freshness targets, service/job design, and backlog.
- Root Compose, README, environment template, and sample CSV.

No test source files, CI workflow, migration tool configuration, frontend component directory, or package-level architecture beyond these files was found. Generated `frontend/trading-dashboard/dist`, `node_modules`, and `backend/trading-core/target` were excluded from source conclusions.

### Read-only runtime verification

| Check | Result |
|---|---|
| `docker compose ps` | PostgreSQL, Redis, Spring backend, FastAPI intelligence, and React/Vite frontend were running. PostgreSQL was healthy. |
| Frontend `http://127.0.0.1:5173/` | HTTP 200. |
| Spring `GET /api/v1/health` | `UP`, `RESEARCH_ONLY`. |
| FastAPI `GET /health` | `UP`, `RESEARCH_ONLY`. |
| FastAPI `GET /api/v1/intelligence/capabilities` | Explicitly reported `live_data_connected=false` and `actionable_recommendations_enabled=false`. |
| Public database tables | 27, matching the known state. |
| `instruments` / `market_candles` | Zero rows. |
| Other analytical/ingestion tables | Aggregate statistics showed no application data. |
| Portfolio | `personal_holdings` contains data; values were not read for this audit. |

Builds and dependency installations were not executed during this audit because the request permits changing only this report. Runtime health is not equivalent to a clean reproducible build or passing test suite.

## 3. Verified system architecture

```text
Browser (localhost:5173)
  └─ React/Vite SPA
       └─ /api proxy only → Spring backend:8080
                              └─ JdbcTemplate → TimescaleDB/PostgreSQL:5432

FastAPI intelligence:8000
  └─ fixed internal HTTP URL → Spring /api/v1/portfolio/holdings

Redis:6379
  └─ no code integration found

External providers / schedulers / workers / brokers
  └─ none connected
```

### Service assessment

| Service | Actual responsibility | Status | Evidence |
|---|---|---|---|
| React/Vite | Manual holdings UI, CSV import, tab persistence, placeholders | **PARTIAL** | `frontend/trading-dashboard/src/main.tsx` |
| Spring Boot | Health, instrument list/search, portfolio CRUD and simple portfolio math | **PARTIAL** | `backend/trading-core/src/main/java/com/trading/api/*` |
| FastAPI | Evidence validation, prototype trap rule, recommendation blockers, portfolio readiness aggregation | **PARTIAL** | `intelligence/app/main.py` |
| PostgreSQL/TimescaleDB | 27-table research-oriented schema; holdings persistence; three hypertables | **PARTIAL** | `infrastructure/postgres/init/*.sql`, live metadata |
| Redis | Container and persistent volume only | **PLACEHOLDER** | `docker-compose.yml`; no Redis client in code |
| Job/ingestion tier | Described in documentation only | **MISSING** | `docs/architecture/services-and-jobs.md` |

### Architectural inconsistencies

1. The architecture documentation lists many logical services, but the runtime contains only a monolithic Spring API and one FastAPI module. There are no schedulers or workers.
2. The frontend proxies `/api` only to Spring (`vite.config.ts`) and has no route to FastAPI, so implemented intelligence endpoints are invisible to the UI.
3. FastAPI calls Spring using a fixed Docker hostname, but Compose does not declare `intelligence.depends_on: backend` or health-based startup ordering. The five-second timeout and 503 handling are reasonable, but startup can be transiently unavailable.
4. Redis is provisioned and persisted but unused.
5. Database initialization uses Docker entrypoint scripts. These run only for a new volume; existing upgrades are manual and there is no schema version table or migration runner.
6. The frontend container runs the Vite development server rather than a production static server. This is acceptable for a private alpha, not for a hardened deployment.
7. `timescale/timescaledb:latest-pg16` is mutable. Base images are referenced by tags rather than immutable digests in source.

## 4. Feature-by-feature implementation matrix

| Capability | Status | Actual implementation |
|---|---|---|
| Manual equity/MF holdings | **IMPLEMENTED** | Upsert, list, delete, CSV import, cost/value/P&L using manual prices. |
| Portfolio retrieval through intelligence service | **IMPLEMENTED** | FastAPI fetches the fixed internal Spring holdings URL, validates response size/schema, and aggregates it. |
| Portfolio concentration checks | **PARTIAL** | Fewer-than-five and over-25%-of-valued-holdings warnings only; no asset/sector/correlation/risk model. |
| Fundamental statement analysis | **MISSING** | No statements/facts schema, parser, ratios, normalization, or UI. |
| Valuation and peer comparison | **MISSING** | No peer universe, valuation facts, or models. |
| Technical indicators | **MISSING** | Schema can store feature JSON, but no calculations or data. |
| Candlestick/chart pattern recognition | **MISSING** | No algorithms, labels, chart library, or annotations. |
| Volume/momentum/trend/liquidity | **PLACEHOLDER** | Design notes and empty tables only. |
| Support/resistance and breakout detection | **PLACEHOLDER** | A request can state `broke_level`; ATLAS does not calculate the level or breakout. |
| False-breakout/trap detection | **PARTIAL** | Six-input deterministic heuristic; inputs are caller supplied; no candles, validation corpus, calibration, persistence, or backtest. |
| Institutional flows and disclosed deals | **PLACEHOLDER** | Tables and design notes only. |
| News/earnings/corporate-event intelligence | **PLACEHOLDER** | News/event and corporate-action tables only; no collector/parser/entity resolution. |
| Global markets/macro/geopolitics | **MISSING** | No provider or code. |
| Governance/accounting/manipulation-risk analysis | **MISSING** | Evidence enum includes governance, but no ingestion or model. Trap warning correctly avoids claiming manipulation. |
| Low/Medium/High risk classification | **PARTIAL** | FastAPI maps submitted evidence severity to preliminary `LOW/MEDIUM/HIGH/UNKNOWN`; this is triage, not calibrated asset or portfolio risk. No UI filter. |
| Bull/base/bear/severe-downside scenarios | **MISSING** | `SCENARIOS` is only an evidence-domain enum. |
| HOLD/ADD/REDUCE/EXIT/WAIT/REBALANCE | **MISSING** | Responses deliberately return `NO_ACTION`; no recommendation policy. |
| Intraday opportunities | **PLACEHOLDER** | UI copy only. |
| Swing opportunities | **PLACEHOLDER** | UI copy only. |
| Short-term opportunities | **PLACEHOLDER** | UI copy only. |
| Long-term opportunities | **PLACEHOLDER** | UI copy only. |
| Mutual-fund analysis/comparison | **PLACEHOLDER** | Holdings accept `MUTUAL_FUND`; no NAV, scheme metadata, benchmark, TER, holdings overlap, drawdown, or comparison. |
| Research dossier with pro/con evidence | **PARTIAL** | Evidence intake distinguishes supporting/contradicting/neutral evidence and timestamps/sources, but does not independently collect evidence or render a dossier. |
| Data provenance and quality | **PLACEHOLDER** | Good schema concepts; no source rows, ingestion runs, validators, or watermarks in use. |
| Backtesting | **MISSING** | Guidance exists, implementation does not. |
| Prediction calibration/performance monitoring | **PLACEHOLDER** | Registry/prediction/outcome tables only. |
| Authentication/authorization | **MISSING** | Localhost binding is the only access boundary. |
| Trade execution | **MISSING (INTENTIONAL)** | No order placement, broker SDK, or execution endpoint found. This must remain absent. |

## 5. Frontend audit

### Functional behavior

`frontend/trading-dashboard/src/main.tsx` is a single 27-line, densely formatted component containing the entire application. Its only data calls are:

- `GET /api/v1/portfolio/holdings`
- `GET /api/v1/portfolio/analysis`
- `POST /api/v1/portfolio/holdings`
- `DELETE /api/v1/portfolio/holdings/{id}`

The **My Portfolio** tab is functional. It supports add/update, delete with browser confirmation, sequential CSV upserts, aggregate summary cards, risk-warning strings, and a holdings table. The CSV parser intentionally rejects embedded commas and is not RFC 4180 compatible. Imports are non-transactional: failure after several rows leaves earlier rows committed. There is no progress report, rollback, batch endpoint, duplicate-row preview, or server-side import validation as a unit.

### Tab/page matrix

| Tab | Status | Finding |
|---|---|---|
| My Portfolio | **PARTIAL** | Functional manual portfolio page; not transaction/lot aware and uses manually entered prices. |
| Mutual Funds | **PLACEHOLDER** | Static copy and offline cards. |
| Intraday | **PLACEHOLDER** | Static copy and offline cards. |
| Swing Trading | **PLACEHOLDER** | Static copy and offline cards. |
| Short-Term Equity | **PLACEHOLDER** | Static copy and offline cards. |
| Long-Term Stocks | **PLACEHOLDER** | Static copy and offline cards. |
| Market & Data Health | **PLACEHOLDER** | Static copy; does not query health, sources, ingestion runs, or quality events. |

### Latest UI changes

The latest visual changes are present in source:

- Gradient/dimensional visual system and responsive rules are in `src/style.css`.
- Active navigation includes `aria-current`.
- Selected tab persistence uses validated `localStorage` key `atlas:selected-tab` and accepts only indexes 0–6 (`main.tsx:9-18`).

The CSS is minified into one source line, which harms reviewability and maintainability. The UI is responsive by CSS breakpoints, but no browser accessibility, keyboard-navigation, color-contrast, or visual-regression test exists.

### Missing frontend connections

- No call to `/api/v1/instruments`.
- No call to any `/api/v1/intelligence/*` endpoint.
- No chart dependency or chart component.
- No candlestick, volume, indicator, support/resistance, pattern, scenario, provenance, or evidence display.
- No risk-tier filter or candidate screener.
- No source timestamp/freshness indicator beyond manual `price_as_of` in the TypeScript type; `price_as_of` is not shown in the table.
- No routing/deep links; tabs are client state only. Persistence works on the same browser/profile but URLs are not shareable.
- No error boundary, request cancellation, retry policy, request timeout, or structured API client.
- A fetch failure is stringified as `Error: ...`, and save/import errors share one global message.

### Frontend readiness conclusion

The current frontend is suitable for a manual portfolio alpha. It should be decomposed only when the first real read models exist; premature page expansion would produce more placeholders. The next UI should expose source health, last successful ingestion, daily candle coverage/gaps, and instrument search before any recommendation surface.

## 6. Spring backend audit

### Implemented APIs

| Endpoint | Status | Notes |
|---|---|---|
| `GET /api/v1/health` | **IMPLEMENTED** | Process-level health response; does not verify DB/provider readiness. |
| `GET /api/v1/instruments` | **PARTIAL** | Bounded limit (1–200), optional `ILIKE` symbol query, prepared parameters. Empty because registry is empty. |
| `GET /api/v1/portfolio/holdings` | **IMPLEMENTED** | Computes invested/value/P&L in SQL. Returns notes as well as holdings. |
| `POST /api/v1/portfolio/holdings` | **IMPLEMENTED** | Validates symbol/type/numeric ranges/notes and performs upsert. |
| `DELETE /api/v1/portfolio/holdings/{id}` | **IMPLEMENTED** | Deletes by numeric ID and returns 404 if missing. |
| `GET /api/v1/portfolio/analysis` | **PARTIAL** | Manual valuation and two heuristic concentration warnings. |

### Strengths

- SQL parameters are bound through `JdbcTemplate`; no direct SQL injection path was found in these controllers.
- Symbol syntax, quantities, costs, manual prices, asset types, and note length are validated in the write path.
- The portfolio result clearly marks recommendations unavailable without verified market data.
- The instrument query clamps result size.

### Gaps and risks

- No service/repository boundary, DTO output model, exception policy, request tracing, metrics, or structured audit log.
- No authentication, authorization, ownership model, CSRF/origin defense, or rate limiting.
- `HealthController` reports `UP` even if PostgreSQL is unavailable; Actuator exists but Compose does not use a backend healthcheck.
- Portfolio writes have no optimistic concurrency/versioning. Holdings are positions, not transactions, so realized P&L, cash flows, tax lots, dividends, and time-weighted/money-weighted returns cannot be derived.
- Concentration uses only currently valued holdings, so missing prices can materially distort weights; the response warns about incompleteness but still emits weights/flags.
- `personal_holdings.symbol` is not linked to `instruments`; symbols can become stale or ambiguous across exchanges.
- Instrument search uses `ILIKE '%query%'`; a larger registry will need normalized prefix/trigram search and appropriate index support.
- No endpoints expose candles, quotes, sources, ingestion status, quality events, features, research dossiers, or signal ledgers.
- No unit, slice, integration, or contract tests exist.

This is prototype-quality application code, not a production-ready research API.

## 7. Intelligence engine audit

### Implemented endpoints

| Endpoint | Status | Finding |
|---|---|---|
| `GET /health` | **IMPLEMENTED** | Process health only. |
| `GET /api/v1/intelligence/capabilities` | **IMPLEMENTED** | Honest feature discovery and live-data/action flags. |
| `POST /api/v1/intelligence/traps/evaluate` | **PARTIAL** | Deterministic heuristic on caller-supplied facts. |
| `POST /api/v1/intelligence/research/evaluate` | **PARTIAL** | Evidence schema, coverage, preliminary severity triage, and hard blockers. |
| `GET /api/v1/intelligence/portfolio/research` | **PARTIAL** | Fetches local holdings, calculates weights, runs empty-evidence readiness checks. |

### Research and safety logic

The evidence model is a good contract seed. It requires domain, factor, source string, timezone-aware non-future timestamp, finding, severity, verification state, and thesis direction. Coverage counts only verified domains. The response correctly states that coverage is not confidence and always blocks action because there is no connected feed or validated model.

The risk classification is **not a risk model**. It maps any critical/high item to `HIGH`, any medium item to `MEDIUM`, complete verified non-risk evidence to `LOW`, and missing/unverified evidence to `UNKNOWN`. It has no volatility, drawdown, liquidity, leverage, quality, valuation, horizon, portfolio covariance, scenario, or calibration input. Calling it “preliminary severity triage” is accurate.

The trap rule scores six booleans and detects a trap when a break and reversal are asserted and at least four booleans are true. ATLAS does not calculate resistance/support, relative volume, wick ratio, VWAP conflict, or range re-entry. There is no timeframe-specific threshold, sample validation, outcome measurement, or false-positive estimate. It is a prototype rule, not pattern recognition or manipulation detection.

### Engineering gaps

- Everything is in `intelligence/app/main.py`; there are no provider, repository, domain, job, or test modules.
- Standard-library `urlopen` is synchronous inside a synchronous FastAPI handler. This is acceptable at tiny local scale but provides no connection pooling, retry/backoff, or circuit breaker.
- Backend URL is fixed, which avoids user-controlled SSRF. Response size is capped at 2 MB and Pydantic validates holdings—both are positive controls.
- No DB connection exists; schema tables for features, traps, models, predictions, signals, and outcomes are never used.
- No asynchronous worker/scheduler, source adapters, feature computation, model artifacts, backtester, or monitoring exists.
- No authentication/rate limit. The evidence endpoint permits up to 500 items with bounded strings, which limits but does not eliminate local resource abuse.
- No automated tests or saved fixtures.

## 8. Database audit

### Verified inventory

The live database contains these 27 public tables:

`alert_deliveries`, `alert_preferences`, `corporate_actions`, `data_quality_events`, `data_sources`, `disclosed_deals`, `exchanges`, `ingestion_runs`, `institutional_flows`, `instrument_features`, `instruments`, `issuers`, `liquidity_events`, `market_candles`, `market_quotes`, `market_sessions`, `model_registry`, `news_articles`, `news_entities`, `news_events`, `participant_position_reports`, `personal_holdings`, `predictions`, `short_sell_disclosures`, `signal_outcomes`, `trading_signals`, and `trap_events`.

`market_quotes`, `market_candles`, and `instrument_features` are TimescaleDB hypertables. The main time-series primary keys and lookup indexes are present. `data_sources.source_code`, portfolio `(symbol, asset_type)`, and instrument `(exchange_id, symbol, series)` have uniqueness constraints.

### Target-table assessment

| Table | Reuse assessment | Gaps before real use |
|---|---|---|
| `instruments` | **REUSE** | Move/copy ISIN semantics from issuer to instrument identifier; add normalized identifiers/aliases and source revision history; define delisting/status rules. Nullable `series` weakens uniqueness because PostgreSQL permits multiple nulls. |
| `market_candles` | **REUSE** | Add/enforce supported timeframes, OHLC invariants, nonnegative volume, canonical-source policy, received/published timestamps, adjustment status, and gap/session validation. PK allows one canonical candle per instant but not parallel raw providers—document that policy. |
| `market_quotes` | **REUSE** | Validate bid/ask/quantities, exchange timestamps, sequence/gap rules, staleness, and provider entitlements. PK by observed time can collide across sources; define canonicalization or source-aware raw storage. |
| `data_sources` | **REUSE** | Populate license scope, contract/version, environment, attribution/display limits, and health state. Existing free-text `license_reference` is insufficient alone for enforceable entitlements. |
| `ingestion_runs` | **REUSE** | Add idempotency key, retry count, source watermark, artifact hash/reference, and structured error/quality summary. Status values need constraints. |
| `data_quality_events` | **REUSE** | Add run/artifact linkage and constrained severity/type taxonomy; index unresolved events and instrument/time queries. |
| `instrument_features` | **REUSE** | JSONB is useful for versioned prototypes, but feature contracts, units, null semantics, provenance/watermarks, and promotion policy are missing. Consider typed read models later, not a duplicate store now. |
| `trading_signals` | **REUSE LATER** | Strong evidence/gate/expiry concept; “trading” name conflicts with research-only positioning but does not execute orders. Add immutable versioning and prohibit actionable publication until model approval. |
| `predictions` | **REUSE LATER** | Add outcome definition, training/universe version, point-in-time lineage, constraint that probabilities are valid and coherent, and indexes for instrument/as-of/horizon. |
| `personal_holdings` | **REUSE** | Preserve existing data. Later add nullable `instrument_id`/scheme identifier with unresolved-symbol workflow; do not require destructive remapping. Transactions/lots require a genuinely separate future ledger if desired. |

### Schema strengths

- Provenance concepts are present throughout: `source_id`, timestamps, revisions, quality states, evidence refs, watermarks, and raw payload fields.
- Signal lifecycle has expiry/invalidation, gate results, evidence references, model link, and outcome table.
- News is separated from entities/events; aggregate institutional flows are separated from disclosed deals and participant reports.
- Corporate actions and market sessions are first-class, which is essential for adjustment and point-in-time correctness.

### Schema deficiencies and drift risks

1. **ISIN modeling:** `issuers.isin` is conceptually incorrect. An issuer can have multiple equity/debt securities; ISIN belongs to a security/instrument. Correct this additively before registry import.
2. **No schema migration system:** `001_init.sql` and `002_portfolio.sql` are create-on-empty-volume scripts. Existing installations require manual changes and have no version ledger, checksum, rollback policy, or preflight backup step.
3. **Few domain constraints:** many status, severity, direction, timeframe, quality, and participant fields are unconstrained strings. Probability ranges/sums and OHLC relationships are not checked.
4. **Incomplete provenance:** freshness guidance requires `event_time`, `published_at`, `received_at`, `source_revision`, license scope, verification state, and payload hash; not every relevant table has these fields.
5. **Canonical versus raw data is undefined:** quote/candle keys effectively choose one row. A raw artifact store and deterministic canonicalization policy are needed; do not duplicate canonical tables.
6. **Index gaps:** unresolved quality events, source status, predictions by instrument/time/horizon, features by instrument/timeframe/version, and corporate actions by instrument/date need workload-driven indexes.
7. **Fundamentals are absent:** there is no table for filing periods, reported facts, taxonomy concepts, units, consolidation scope, restatements, or derived ratios. These will be genuinely necessary later.
8. **Mutual-fund master is absent:** `personal_holdings` can label a fund but cannot identify AMFI scheme/plan/option, benchmark, AMC, category, or NAV series.

No duplicate tables should be created merely to bypass these gaps. Extend the existing model additively and introduce new tables only for concepts not represented (for example, instrument identifiers, immutable ingestion artifacts, financial facts, mutual-fund scheme master, and portfolio transactions if transaction accounting is later approved).

## 9. Data-provider assessment

Provider facts were reviewed on 13 November 2026. Prices, entitlements, rate limits, file formats, and terms can change; legal/contract review remains required before automation or redistribution. “Publicly downloadable” does not automatically mean unrestricted automated reuse or redistribution.

| Need | Candidate | Cost/access and coverage | Freshness/reliability | Suitability and limitations |
|---|---|---|---|---|
| NSE instruments/identifiers | [NSE securities available for trading](https://www.nseindia.com/static/market-data/securities-available-for-trading) and [security master documentation](https://nsearchives.nseindia.com/web/sites/default/files/inline-files/NSE-Masters%20Data-v1.6.pdf) | Public exchange files include symbol, series, token/security code and ISIN-related masters; exact automation rights governed by NSE policy. | Exchange-primary; daily/current files. | Best registry seed for NSE. Version and diff every artifact; do not scrape HTML as the system of record. Confirm automated download and retention terms. |
| NSE EOD OHLCV/corporate actions | [NSE reports/downloads](https://www.nseindia.com/all-reports/) and [data/reports guide](https://www.nseindia.com/static/products-services/equity-market-data-reports-download) | Public reports include UDiFF bhavcopy and corporate-action reports; NSE also offers [paid EOD/historical subscriptions](https://www.nseindia.com/static/market-data/eod-historical-data-subscription). | Final EOD exchange data; report revisions are possible. | Suitable for initial daily research/backfill if terms allow. Not a live intraday feed. Preserve filenames, hashes, publication/receipt time, and corrections. |
| NSE real-time/intraday | [NSE real-time data](https://betanseapi.nseindia.com/static/market-data/real-time-data-subscription) and [NSE data policy](https://www.nseindia.com/static/market-data/nse-data-policy) | Licensed Level 1/2/3, tick-by-tick, stock-wise and snapshot products; tariffs/agreements apply and can be substantial. | Exchange-primary with product-specific latency. | Correct production route for strict intraday research, subject to contract and local display/storage rights. Free website endpoints are not a substitute. |
| BSE identifiers, EOD, corporate/fundamental data | [BSE Information Products tariff](https://www.bseindia.com/downloads1/Information_Products_Pricing_Sheet.pdf) | BSE advertises real-time, delayed, EOD, historical, reference, corporate announcements, financial results, actions, governance, shareholding and pledge data. Pricing is tariff/contract based and tax exclusive. | Exchange-primary. | Strong BSE source; obtain the current contract and machine-readable specifications. Do not assume website pages permit bulk ingestion. |
| Lower-cost personal Indian live/historical feed | [Zerodha Kite Connect pricing](https://support.zerodha.com/category/trading-and-markets/general-kite/kite-api/articles/what-are-the-charges-for-kite-apis) | Official page lists Personal as free without live/historical data and Connect at ₹500/month per app with WebSocket real-time and historical candles, subject to account and current terms. | Broker-distributed; practical for personal use, not an exchange archival source. | Possible local prototype adapter. **Risk:** the same platform exposes order APIs. Use a data-only credential boundary/adapter, do not include order scopes/code, and verify storage/redistribution rights. Not the preferred foundation for autonomous intraday recommendations without entitlement review. |
| Corporate filings/fundamentals | [NSE corporate filings](https://www.nseindia.com/companies-listing/corporate-filings-application?id=eqFinResults), BSE corporate products, and issuer filings | Public NSE UI exposes announcements, actions, financial results, board meetings and shareholding; BSE sells structured corporate data. | Primary disclosures; may be revised/restated and reported at different consolidation scopes. | Start from XBRL/structured exchange filings, retain original documents and revision chain, and reconcile NSE/BSE. Ratios must never mix standalone/consolidated or incompatible periods. MCA filing access/fees and bulk-use terms require separate verification before use. |
| FII/DII and disclosed transactions | NSE FII/DII reports plus [bulk/block deal archive](https://www.nseindia.com/report-detail/display-bulk-and-block-deals); corresponding BSE reports | Public disclosure reports; bulk/block data can be corrected. | Aggregate flows are usually publication-window/EOD data; large deals are disclosed after market as specified by the exchange. | Useful context, not proof of stock-level institutional accumulation or manipulation. Preserve provisional/final state and never infer intraday order flow from aggregate reports. |
| Mutual-fund NAV | [AMFI NAV download](https://www.amfiindia.com/net-asset-value/nav-download) | Official downloadable current/history data; the page states historical downloads are limited to 90 days per request. No API SLA is stated. | Official daily end-of-day NAV; not minute-by-minute. | Suitable for personal EOD NAV ingestion with respectful scheduling, caching and artifact preservation. Verify terms for automated bulk use. |
| Mutual-fund metadata/portfolio/risk | AMFI/AMC disclosures and SEBI-required portfolio/riskometer disclosures | Public documents/spreadsheets; formats differ by AMC and period. | NAV daily; portfolios generally periodic and lagged; risk/performance disclosures follow regulatory schedules. | Requires a scheme/plan/option master, ISIN mapping, document normalization, and revision handling. Never treat lagged holdings as current. |
| Indian macro | [RBI Database on Indian Economy](https://data.rbi.org.in) / [RBI handbook description](https://www.rbi.org.in/scriptS/PublicationsView.aspx?id=24094) | Public research portal; official material describes current/historical validated RBI datasets. API/bulk endpoint stability and terms need per-series verification. | Publication-specific; authoritative for RBI series. | Preferred India macro source. Store release vintage and revision, not only latest value. |
| Global macro | [World Bank Indicators API](https://datahelpdesk.worldbank.org/knowledgebase/articles/889392) and [IMF Data APIs](https://data.imf.org/en/Resource-Pages/IMF-API) | World Bank V2 needs no API key and covers nearly 16,000 series; IMF exposes SDMX 2.1/3.0 APIs, with portal/account details varying. | Official but mostly lower-frequency macro data. | Suitable for macro context, not live market regime. Preserve dataset/version and observation status. |
| US/global macro convenience | [FRED API terms](https://fred.stlouisfed.org/docs/api/terms_of_use.html) | API key required; official docs state rate limiting and attribution/terms requirements. Some underlying series have additional terms. | Series-dependent and often revised. | Useful aggregator, but provenance must retain the original source and release vintage. |
| Global market prices | [Alpha Vantage documentation](https://www.alphavantage.co/documentation/) / [premium limits](https://www.alphavantage.co/premium/) | Free tier is documented at 25 requests/day; premium unlocks higher limits and selected real-time/delayed entitlements for personal use. Commercial use requires sales contact. | Coverage/freshness depends on endpoint and entitlement. | Adequate for exploratory global EOD context, not a universal strict real-time source. Validate symbols, adjustments, exchange entitlements, and SLA. |
| Institutional global market data | [LSEG real-time developer overview](https://developers.lseg.com/en/use-cases-catalog/real-time) | Quote/contract based; normalized data across many venues/instruments, with real-time and historical/tick offerings. | Enterprise-grade subject to subscribed venue entitlements/SLA. | Strong long-term option if budget justifies it; contract, display, derived-data and storage rights are decisive. |
| Global news discovery | [GDELT Project terms/about](https://gdeltproject.org/about.html) | Core GDELT datasets are described as open and reusable with citation. Underlying publisher content remains subject to publisher rights; newer GDELT Cloud plans have separate terms. | Broad, near-real-time discovery; extraction/noise/source quality varies. | Use for discovery/event candidates only. Do not store/display copyrighted full text without rights, and do not use GDELT tone alone for recommendations. Pair with official filings and a licensed news feed for high-stakes dossiers. |

### Provider decision

For the immediate milestone, use official NSE/BSE instrument and EOD artifacts under confirmed personal-research terms, plus AMFI for mutual-fund NAV only after the equity pipeline is reliable. Do **not** build intraday recommendations on an undocumented/free endpoint. A live-feed decision requires a written entitlement matrix covering personal use, machine access, storage duration, derived data, display, redistribution, historical backfill, rate limits, correction policy, and SLA.

## 10. Critical gaps and risks

### Critical path gaps

1. **No data plane:** no instruments, sources, candles, quotes, sessions, actions, or ingestion runs exist in application data.
2. **No automated tests or CI:** every behavior and safety claim can regress unnoticed.
3. **No migration discipline:** changes against an existing volume are manual and risky.
4. **No point-in-time research data:** fundamentals, news, events, corporate actions, and universe membership cannot be reconstructed for backtests.
5. **No frontend/intelligence integration:** even prototype research output cannot be displayed.

### Financial/research risks

- Look-ahead bias is currently unavoidable because no backtester or vintage/revision store exists.
- Survivorship bias will occur if only current instruments are imported; delisted/renamed securities and historical universe membership must be retained.
- Corporate-action adjustment policy is undefined. Raw and adjusted prices must be separate and versioned.
- Manual portfolio prices can be stale and materially distort concentration/P&L.
- The trap heuristic can be mistaken for a predictive/manipulation detector if surfaced without its warnings.
- Evidence `quality="VERIFIED"` is caller asserted today; there is no cryptographic/artifact or provider verification behind it.
- Signal/prediction tables exist before validated models. They must remain unpublished/disabled by default.

### Security and operational risks

- `.env` had mode `0644`, used the documented default DB password, and the repository has no `.gitignore`. No secret value is included here.
- APIs have no identity, authorization, rate limit, request audit, or explicit origin/host policy.
- Loopback port binding materially reduces exposure, but it is not authorization and does not address malicious local processes, browser-origin attacks, or accidental reverse proxying.
- PostgreSQL volume data is not encrypted at rest by ATLAS; protection depends on host/FileVault controls.
- The frontend dev server and mutable image tags are not production hardening.
- No backup/restore verification, migration backup gate, retention policy, or disaster-recovery exercise exists.
- No dependency/security scan is configured; dependency vulnerability state is therefore **UNVERIFIED** in this audit.
- No outbound allowlist or provider-domain policy exists because no collectors exist yet. Add one before external ingestion.

### Positive safety findings

- Ports are bound to `127.0.0.1` in Compose.
- No broker library, order endpoint, trade-execution routine, or autonomous transaction path was found.
- FastAPI uses a fixed backend URL rather than accepting arbitrary fetch URLs.
- Recommendation responses are hard-blocked and explicitly non-actionable.
- Design documents correctly require completed candles, freshness, provenance, calibrated probabilities, realistic costs, point-in-time data, and rejection when evidence is insufficient.

## 11. Prioritized development roadmap

### M0 — Safety, migrations, and test harness

**Dependencies:** none.  
**Work:** establish schema versioning/baseline for the existing volume; add test directories and CI; protect `.env`; add health/readiness checks; pin deployable images; document backup/restore.  
**Database:** additive migration ledger/baseline only; no destructive reinitialization.  
**Tests:** Spring controller/JDBC integration tests with Testcontainers; FastAPI unit/API tests; frontend unit smoke tests; Compose health smoke test.  
**Acceptance:** a fresh database and a preserved existing database converge to the same schema; portfolio rows survive migration; all tests run from one documented command; secrets are ignored and file permissions documented.

### M1 — Instrument registry, sessions, corporate actions, and daily EOD candles (recommended now)

**Dependencies:** M0 migration/test baseline; confirmed NSE/BSE usage terms.  
**Work:** import versioned exchange security masters, normalize symbols/series/ISINs, preserve renames/delistings, populate sources, ingest exchange calendars/actions, backfill daily OHLCV, validate and quarantine bad rows, expose coverage/source health.  
**Database:** reuse existing tables; add instrument identifier/history support, artifact hashes/revisions, and missing constraints/indexes. Do not add duplicate instrument/candle tables.  
**Tests:** golden-file parsers, idempotent replay, malformed/partial file handling, OHLC/volume/session rules, rename/delisting fixtures, revision tests, DST/timezone checks, API contract tests.  
**Acceptance:** rerunning the same artifact writes no duplicates; every canonical candle links to a source/run/artifact; gaps and corrections are visible; no incomplete/unverified candle is eligible for analytics.

### M2 — Daily features and chart/read-model integration

**Dependencies:** complete validated M1 history.  
**Work:** versioned returns, ATR, moving averages, RSI, momentum, liquidity proxies, support/resistance candidates, deterministic chart API, candlestick/volume UI with provenance and gap overlays.  
**Database:** reuse `instrument_features`; add typed read models only if measured query needs justify them.  
**Tests:** independent numerical fixtures, warm-up/null behavior, split-adjustment tests, no-future-data assertions, visual/component tests.  
**Acceptance:** features reproduce from a pinned data snapshot; each UI point exposes source time/version; no calculation reads data after its `as_of`.

### M3 — Fundamentals, governance, peers, and institutional disclosures

**Dependencies:** stable instrument/issuer identity and provider contracts.  
**Work:** ingest XBRL/filings, distinguish standalone/consolidated and period type, model restatements, calculate versioned ratios, build point-in-time peer groups, ingest FII/DII and large-deal disclosures without conflating them.  
**Database:** new financial filing/period/fact tables are genuinely required; reuse existing corporate/institutional tables.  
**Tests:** XBRL taxonomy/unit fixtures, restatement/revision tests, ratio reconciliation to filings, peer membership as-of tests.  
**Acceptance:** every ratio traces to filing facts and units; revisions retain prior versions; no report is used before publication time.

### M4 — Mutual-fund research

**Dependencies:** source/provenance framework and scheme identifier design.  
**Work:** AMFI scheme/plan/option master, daily NAV, benchmark/category, TER, riskometer, periodic portfolio holdings, rolling returns/drawdowns, overlap and concentration.  
**Database:** add mutual-fund scheme/plan and NAV structures or generalize instruments carefully; do not encode plan/option identity only in free-text symbols.  
**Tests:** scheme-code changes, direct/regular and growth/IDCW separation, missing NAV calendars, benchmark alignment, holdings-lag warnings.  
**Acceptance:** comparisons never mix plan/option variants; displayed holdings show disclosure date/lag; NAV freshness is EOD, not “live.”

### M5 — News, earnings, macro, and event intelligence

**Dependencies:** licensed source decision and entity resolution based on stable instruments/issuers.  
**Work:** official filing events first, then licensed news/GDELT discovery, canonical URL/hash dedupe, entity resolution, event taxonomy, source trust, macro release calendar and vintage store.  
**Database:** reuse news/entity/event tables; extend provenance and add macro release/observation vintage tables if needed.  
**Tests:** duplicate clusters, timestamp/publication ordering, entity ambiguity, corrections/retractions, copyrighted-content retention policy.  
**Acceptance:** dossier distinguishes official filings from media; all events show source and publication/receipt time; unsupported full text is not stored.

### M6 — Risk, scenarios, and research dossiers

**Dependencies:** M2–M5 data coverage.  
**Work:** horizon-specific risk framework, liquidity/drawdown/quality/valuation/governance dimensions, bull/base/bear/severe scenarios, thesis/antithesis, assumptions, alternatives, invalidation and uncertainty; keep actions non-actionable until validation.  
**Database:** versioned dossier/evidence snapshots may be necessary; reuse signal evidence/gates where appropriate.  
**Tests:** deterministic policy tests, missing-data blockers, conflicting evidence, stale-source suppression, scenario invariants.  
**Acceptance:** incomplete/stale evidence returns `NO_ACTION`; every conclusion has supporting/opposing evidence, source timestamps, assumptions, risks, invalidation, and alternatives.

### M7 — Backtesting, calibration, and monitored research actions

**Dependencies:** point-in-time M1–M6 history and explicit outcome definitions.  
**Work:** survivorship-aware universes, walk-forward splits, realistic fees/slippage, corporate actions, untriggered/expired signals, probability calibration, model registry/approval/rollback, paper-observation period.  
**Database:** reuse model/prediction/signal/outcome tables; add immutable experiment/run datasets and universe snapshots if absent.  
**Tests:** temporal leakage tests, reproducibility, cost sensitivity, delisting handling, calibration confidence intervals, benchmark comparisons.  
**Acceptance:** a third party can reproduce a result from immutable versions; out-of-sample net performance and calibration are reported with uncertainty; model promotion requires explicit approval.

### M8 — Optional licensed intraday research

**Dependencies:** licensed feed with explicit storage/display rights, robust M7 governance, operational monitoring.  
**Work:** WebSocket adapter, heartbeat/reconnect, complete candle builder, quote sequence/gap repair, market-session controls, latency/staleness suppression, depth only if licensed.  
**Database:** reuse quotes/candles/runs/quality events; raw high-volume retention requires a deliberate storage/retention design.  
**Tests:** disconnect/replay, out-of-order/duplicate ticks, clock skew, late corrections, incomplete candle suppression, exchange halts/circuits.  
**Acceptance:** stale or incomplete data deterministically suppresses research output; no order API or broker execution permission exists; operational and licensing controls are audited.

## 12. Recommended immediate milestone and exact files

### Recommendation

Implement **M0 + the first bounded slice of M1**: safe migrations, source registry, NSE/BSE instrument master import, daily session/action import, and validated daily EOD candles. Stop before technical signals or recommendations.

### Existing files to change

| File | Required change |
|---|---|
| `docker-compose.yml` | Add ingestor configuration/health ordering and an explicit read-only data-provider credential boundary if needed; retain loopback ports and volumes. |
| `.env.example` | Add non-secret provider/config variable names only; document local paths and scheduling. |
| `.gitignore` (new) | Exclude `.env`, credentials, raw licensed artifacts if contract requires, generated data, builds and editor files. |
| `README.md` | Document provider terms prerequisites, backup/migration flow, ingestion commands, and research-only limitations. |
| `infrastructure/postgres/init/001_init.sql` | Keep the fresh-install baseline aligned only after a migration strategy is established; do not edit as the sole upgrade mechanism. |
| `infrastructure/postgres/migrations/V003__instrument_provenance.sql` (new; exact naming may follow selected migration tool) | Additive correction for instrument ISIN/identifiers, artifact/run provenance, domain constraints, and indexes. Preserve all holdings. |
| `backend/trading-core/pom.xml` | Add the selected migration/test tooling and Testcontainers dependencies. |
| `backend/trading-core/src/main/resources/application.yml` | Configure migrations/readiness without embedding secrets. |
| `backend/trading-core/src/main/java/com/trading/api/InstrumentController.java` | Return stable IDs, ISIN/type/source/status and add bounded detail/coverage endpoints or delegate to a new service. |
| `backend/trading-core/src/main/java/com/trading/api/DataHealthController.java` (new) | Read-only source/run/quality/candle coverage API for the dashboard. |
| `backend/trading-core/src/test/...` (new) | Migration, repository, controller, and preserved-portfolio integration tests. |
| `intelligence/requirements.txt` | Add only audited HTTP/database/parser dependencies required by the adapter. |
| `intelligence/app/main.py` | Register health/status routes and application lifecycle; move ingestion logic out of this file. |
| `intelligence/app/config.py` (new) | Typed configuration with safe defaults and allowlisted provider hosts. |
| `intelligence/app/providers/nse.py` (new) | NSE master/EOD/action download and parse adapter. |
| `intelligence/app/providers/bse.py` (new, only after contract/specification) | BSE adapter. |
| `intelligence/app/ingestion/instruments.py` (new) | Normalize, diff, version, and idempotently upsert registry records. |
| `intelligence/app/ingestion/eod_candles.py` (new) | Artifact-driven daily candle import and correction handling. |
| `intelligence/app/quality/market_data.py` (new) | OHLC, volume, session, duplicate, gap, revision, and freshness validation. |
| `intelligence/app/repositories/postgres.py` (new) | Transactional writes to existing registry/provenance/candle tables. |
| `intelligence/tests/...` (new) | Golden artifacts, parser, replay/idempotency, correction, and quality-gate tests. |
| `frontend/trading-dashboard/src/main.tsx` | Connect instrument/data-health read models; preferably split during this milestone. |
| `frontend/trading-dashboard/src/api/client.ts` (new) | Typed, timeout-aware API calls. |
| `frontend/trading-dashboard/src/pages/DataHealthPage.tsx` (new) | Source/run/quality/gap UI; replace current placeholder. |

The exact migration tool should be chosen before implementation. Flyway fits Spring well, but the selected process must baseline the existing 27-table database without recreating it and must be the single authority for future schema upgrades.

### Immediate milestone acceptance criteria

1. Existing portfolio data is backed up, migrated additively, and unchanged by a verified checksum/count comparison.
2. Each imported instrument has exchange, symbol, series/type, security identifier where available, active validity interval, source, and revision lineage.
3. A replay of the same file is idempotent.
4. Symbol changes/delistings retain history rather than overwriting identity.
5. Each daily candle is complete, session-aligned, source-linked, quality-classified, and traceable to a hashed artifact/run.
6. OHLC violations, negative volumes, duplicates, gaps, unknown symbols, and late corrections are quarantined/logged.
7. Data Health UI shows last success/failure, source, license reference, artifact date, row counts, gaps, unresolved quality events, and latest complete candle.
8. No recommendation, signal, probability, or order capability is introduced.

## 13. Build and test commands

These are the recommended commands; they were not all executed during this audit-only task.

### Current project

```bash
# Frontend reproducible install/build
cd frontend/trading-dashboard
npm ci
npm run build

# Spring compile/tests (currently no test sources)
cd ../../backend/trading-core
mvn test

# Python syntax/import smoke; add pytest in M0
cd ../../intelligence
python -m compileall app

# Full local stack
cd ..
docker compose up --build -d
docker compose ps

# Read-only health checks
curl -fsS http://127.0.0.1:5173/ >/dev/null
curl -fsS http://127.0.0.1:8080/api/v1/health
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/api/v1/intelligence/capabilities
```

### Required after M0/M1

```bash
# Frontend tests (add script in M0)
npm test

# Backend unit/integration/migration tests
mvn verify

# Intelligence unit/integration tests
pytest -q

# Compose smoke and provider-adapter replay using checked-in synthetic fixtures
docker compose up --build -d
./scripts/smoke-test.sh
./scripts/replay-fixture-test.sh
```

Tests must use synthetic or contract-permitted fixtures, never personal holdings or redistributable licensed payloads in the repository. Live-provider tests should be opt-in, rate-limited, credential-safe, and excluded from ordinary CI.

## Final readiness judgment

ATLAS has a useful local portfolio slice, a good safety vocabulary, and a forward-looking schema. It is **not implementation-ready for autonomous recommendations** because identity, market data, provenance execution, tests, point-in-time fundamentals/events, analytical validation, and UI integration do not exist. It **is ready for a disciplined data-foundation milestone** provided migration safety and provider licensing are handled first.

The correct sequence is: preserve data → establish migrations/tests → import identities/sessions/actions → ingest and validate EOD history → expose source health → compute reproducible features → add fundamentals/events → build dossiers/risk/scenarios → backtest/calibrate → consider research actions. Intraday data and any action labels belong near the end, not the beginning.
