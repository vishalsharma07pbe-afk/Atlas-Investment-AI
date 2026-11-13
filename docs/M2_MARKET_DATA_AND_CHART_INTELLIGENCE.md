# M2: Market data and chart intelligence

Verified on 2026-11-13. This milestone adds a provider-independent research and charting layer on top of the validated M1 registry and daily OHLCV store. It does **not** claim a live feed, recommendation engine, or successful real-market-data import.

## Completion status

Completed:

- Additive Flyway v4 migration for security names, symbol history, and feature provenance/revision metadata.
- Searchable NSE/BSE instrument API with symbol, name, ISIN, exchange filters, listing status, source, and source revision.
- Completed-daily-candle and freshness APIs; only validated manual daily records are eligible.
- Provider-independent daily technical analysis, deterministic pattern detection, support/resistance levels, adjustment warnings, and honest insufficient-data states.
- Stock Explorer with instrument search, candlesticks, volume, optional moving averages, freshness/source display, explainable patterns, and research-only summaries.
- TradingView Lightweight Charts attribution.
- Premium Liquid Glass refinement, fixed sidebar, non-overlapping desktop appearance drawer, sticky mobile navigation, responsive grids/tables, reduced-motion support, and persisted theme/opacity/blur/border settings.
- Automated backend, intelligence, and frontend coverage.

Blocked by provider access:

- Automatic or scheduled NSE/BSE ingestion remains disabled.
- No provider credentials or verified account entitlement were available.
- No licensed exchange file was supplied for manual import.
- Production therefore remains `MANUAL_CSV_ONLY`; no synthetic prices are inserted.

## Provider and legal boundary

The code includes a disabled adapter for the documented Upstox V3 historical-candle API. It requires an explicit access token, fixed official host, rate limiting, retries, response caps, and treats returned candles as `RAW_UNADJUSTED`. It is not scheduled and does not write directly to production. Upstox access and instrument coverage depend on authenticated account entitlements: <https://upstox.com/developer/api-documentation/get-historical-candle-data/>.

Official exchange material identifies historical/EOD data as governed or subscription products. Operators must verify their own rights before importing or retaining files:

- NSE data policy: <https://www.nseindia.com/static/market-data/nse-data-policy>
- NSE EOD/historical subscription: <https://www.nseindia.com/static/market-data/eod-historical-data-subscription>
- BSE information-products pricing: <https://www.bseindia.com/downloads1/Information_Products_Pricing_Sheet.pdf>

ATLAS does not scrape protected endpoints. The strict M1 CSV path remains the production ingestion mechanism until credentials, licensing, exchange mappings, and operational approval are configured.

## Analysis behavior

Calculated from completed daily candles only:

- SMA 20/50/100/200 and EMA 9/20/50/200
- RSI 14 using Wilder smoothing
- MACD 12/26/9
- Bollinger Bands 20/2
- ATR 14 and ADX 14
- Relative volume 20, OBV, 1/20-session momentum, and annualized 20-session historical volatility
- Local-extrema support and resistance
- Rule-based candlestick, breakout/breakdown, false-breakout, volume breakout, double top/bottom, head-and-shoulders, and triangle observations

Each pattern includes its detection timestamp, candle references, explanation, confirmation state, and invalidation condition. Confirmation never reads future candles. True VWAP is deliberately unavailable from daily OHLCV because it requires intraday price/volume observations. Raw and adjusted histories are never silently mixed or interpreted as equivalent.

The output is descriptive research evidence, not a buy/sell recommendation.

## APIs

- `GET /api/v1/instruments?q=&exchange=&limit=`
- `GET /api/v1/market-data/instruments/{id}/candles?limit=`
- `GET /api/v1/market-data/instruments/{id}/freshness`
- `GET /api/v1/data-health/summary`
- `GET /api/v1/intelligence/providers/status`
- `GET /api/v1/intelligence/technical/{instrumentId}`
- `GET /api/v1/intelligence/technical/{instrumentId}/summary`

The frontend proxies `/api` to trading-core and `/intelligence` to the intelligence service.

## Liquid Glass verification

- Dark, Light, and Auto modes are selectable; Auto follows the operating-system/browser color preference.
- Automated rendering checks cover 0%, 25%, 50%, 75%, and 100% panel alpha.
- At 0%, panel/floating-surface background is transparent and effective blur is forced to `0px`; text and content remain fully opaque.
- Blur persists independently from 0–40px and resumes when opacity rises above zero.
- The subtle border is independent of opacity.
- The appearance drawer reserves desktop layout space and becomes a modal below 1320px, avoiding card/control overlap.
- The desktop sidebar remains viewport-fixed via sticky positioning; compact mobile navigation remains sticky at the top.
- Dark/light ambient gradients are animated with compositor-friendly transforms and disabled by `prefers-reduced-motion`.
- Tables retain horizontal scrolling, Stock Explorer prioritizes chart width, and card grids collapse at tablet/mobile breakpoints.

### Form and control refinement (2026-11-14)

- Replaced arbitrary inline field widths with shared full-width `field`, `control-grid`, `editor`, and `form-actions` layout primitives.
- Paired date/number fields now use equal columns; related JSON editors use symmetrical two-column or full-width layouts.
- Labels, supporting hints, input heights, padding, focus rings, borders, and button rows now follow one consistent rhythm.
- Restored the native `hidden` behavior for file inputs so browser “Choose File” controls no longer leak through the custom upload cards.
- JSON and CSV editors use a readable monospaced treatment with controlled minimum heights and responsive wrapping.
- Below 780px, all multi-column form groups collapse to a single column and actions become full-width.

## Production verification and actual data

Persistent database after migration:

- Flyway version: `4`
- Portfolio holdings: `1`
- Holdings checksum before and after: `26264b669a95cc3c50d2c02bf81a7c92`
- Instruments: `0`
- Validated daily candles: `0`
- Derived feature rows: `0`
- Imported sources: none
- Date coverage: none
- Import failures: none during M2 (no production import was attempted)

Backup: `backups/atlas_pre_m2_20261113.dump` (SHA-256 `1612e51be75a4d63dda36c6e37c2ee5d93732bf3ec661bc62b6528f3af10ea40`). Docker volumes were not removed or recreated.

Running checks returned:

- trading-core health: HTTP 200
- Data Health summary: HTTP 200, `liveMarketDataConnected=false`
- provider status: HTTP 200, `configured=false`, `automatic_refresh_enabled=false`, `live=false`
- empty instrument searches: HTTP 200 with `[]`
- unknown technical instrument: HTTP 404

## Test and build results

- Backend Spring integration suite: passed (3 tests), including v2 baseline through v4, registry/search, validation, idempotency, rejection/quality reporting, candle API, and Data Health API.
- Intelligence `unittest` suite: passed (4 tests), covering numerical indicator warm-up/accuracy, deterministic levels, no-future confirmation, and insufficient/mixed-adjustment API states.
- Frontend Vitest suite: passed (3 tests), covering truthful empty state, opacity/blur checkpoints, and all theme modes.
- Frontend TypeScript/Vite production build: passed (35 modules).
- Docker builds: backend, intelligence, and frontend passed.
- `npm audit`: 0 vulnerabilities after upgrading the test-only Vitest dependency; production audit also reports 0.

## Commands used

```sh
npm --prefix frontend/trading-dashboard test
npm --prefix frontend/trading-dashboard run build
npm --prefix frontend/trading-dashboard audit
docker compose build backend intelligence frontend
docker compose up -d --no-deps backend
docker compose up -d intelligence frontend
docker compose exec -T postgres psql -U trading -d trading -c "...count and checksum queries..."
docker run --rm --network atlas_default ... maven:3.9-eclipse-temurin-21 mvn test -q
docker run --rm -v "$PWD/intelligence/tests:/app/tests:ro" atlas-intelligence python -m unittest discover -s tests -v
```

## Changed files

- Configuration: `.env.example`, `docker-compose.yml`
- Migration/data template: `backend/trading-core/src/main/resources/db/migration/V4__chart_intelligence_read_models.sql`, `data/templates/instruments.csv`
- Backend: `InstrumentController.java`, `MarketDataController.java`, `DataImportService.java`, `DataFoundationIntegrationTest.java`, `test-schema.sql`
- Intelligence: `config.py`, `market_client.py`, `main.py`, `technical.py`, `patterns.py`, `providers/__init__.py`, `providers/upstox.py`, `tests/test_technical.py`
- Frontend: `package.json`, `package-lock.json`, `vite.config.ts`, `main.tsx`, `style.css`, `StockExplorer.tsx`, `StockExplorer.test.tsx`
- Documentation: `README.md`, this file

## Next milestone

Obtain and document a provider agreement/account entitlement, supply credentials outside source control, map provider instrument keys to registry records, validate a small licensed sample in a staging database, compare revisions/corporate actions, and obtain operator approval before enabling any scheduled production import. Until then, use the audited manual CSV workflow only.
