# Integrated Daily Market Intelligence

This release combines a complete **read-only daily intelligence vertical**: backend registry and validated candle retrieval, strict Python evidence gates, multi-factor ranking, anomaly heuristics, a React dashboard and automated tests.

## API

`GET /api/v1/intelligence/market/overview?exchange=NSE&limit=20&max_age_days=7`

The endpoint reads up to 20 instruments from the existing registry and at most 250 daily candles per instrument. It runs on demand, without polling, scheduling, external uploads or trade execution. The output includes:

- Five gainers and decliners, 20-day momentum leaders, relative-volume leaders, and up to ten anomaly-watch candidates **within the sampled universe only**.
- Daily sampled breadth: advancing, declining, unchanged.
- One-day close change, 20-day momentum, relative volume versus the prior 20 sessions, RSI, ATR as percentage of close and trend classification.
- Potential failed upside/downside breaks, 20-day closing breakouts, unusual volume, large daily moves and wick warnings.
- Per-category exclusions and an explicit notice that these are not live market-wide rankings or recommendations.

## Data quality and limitations

Requires at least 50 daily candles per instrument, strictly increasing dates, consistent recognized `RAW_UNADJUSTED` or `ADJUSTED` status, valid OHLCV, completed indicators and last candle within the specified age limit. Unverified Upstox preview candles cannot enter this engine. The indicator calculations are historical observations, not validated predictions. No fundamentals, corporate action verification, liquidity, spread, institutional flows or news are incorporated into the rankings.

A failed-breakout candidate is **not** evidence of market manipulation. Relative volume is not exchange-wide volume. The default seven-calendar-day freshness window is not an intraday or exchange-session SLA. Provider errors are counted as skipped records rather than replaced with fabricated values.

## Verification

`cd intelligence && python3 -m unittest discover -s tests -v`

`cd frontend/trading-dashboard && npm ci && npm test && npm run build`

The UI replaces the earlier narrow screener in the intraday/swing/short-term tabs, but the analysis itself is **daily only**, not an intraday signal. The legacy daily screener API remains available for compatibility.
