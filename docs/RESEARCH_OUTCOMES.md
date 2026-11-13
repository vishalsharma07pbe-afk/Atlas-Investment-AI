# Historical broker research outcome review

The `POST /api/v1/intelligence/research/brokers/outcomes` API evaluates **user-supplied** research reports from Groww, Zerodha, Upstox, Angel One and other supported sources against **user-supplied** daily close prices.

Input: stable `instrument_id`, up to 200 `reports` using the existing broker research schema, up to 3,000 `prices` with `trade_date`, positive `close`, `adjustment_status` and `source_revision`, optional `as_of`, `horizon_days` (5–730) and bounded entry/exit delays.

Method: the entry is the first eligible close **strictly after** report publication, within the permitted entry delay. The exit is the first eligible close on/after the calendar-day horizon, within the exit delay. Immature horizons, missing closes, mixed price adjustments and mismatched source revisions prevent a return calculation. Duplicate dates and future-dated inputs are rejected. There is no intraday or same-publication-day fill, avoiding a common lookahead error.

Outputs: per-report dates, rating, unverified observed price return where comparable, blockers, and no verified analyst accuracy score. **A price return is not a rating accuracy score**; dividends, fees, survivorship bias, split/corporate-action verification, report authenticity and total-return adjustments remain unresolved. All rows explicitly carry a provenance blocker and `accuracy_verified:false`.

No broker research feeds or price feeds are connected by this feature. No automated collection, order placement, advice or fabricated broker ratings.

Tests: `cd intelligence && python3 -m unittest discover -s tests -v` and `cd frontend/trading-dashboard && npm test && npm run build`.
