# ATLAS P2 Research Lab — implementation status

Updated: 2026-11-19

P2 extends the existing evidence-first research stack. It does not enable order execution, fabricate missing factors, or convert historical simulations into recommendations.

## Implemented

### Grounded research assistant

- Natural-language stock and mutual-fund research questions over a bounded evidence pack.
- Optional use of any configured ATLAS AI provider with a strict structured-output schema.
- Every model finding must cite one or more supplied evidence IDs; unsupported citations are rejected.
- Evidence-only fallback when no model is configured or a model response fails validation.
- Visible evidence coverage, dated sources, missing domains, stale observations, and uncertainty.
- Sensitive-token patterns are rejected before a prompt can be sent to a provider.

### Walk-forward signal evaluation

- Rolling train/test folds with the training period strictly preceding the test period.
- Features use completed daily closes and outcomes use the following session.
- No random shuffle, same-session outcome, or full-sample threshold fitting.
- Directional accuracy, Brier score, calibration buckets, turnover, transaction-cost assumption, and buy-and-hold comparison.
- Mixed adjustment series, invalid prices, duplicate dates, and insufficient history fail closed.

### Advanced screening

- Combined technical, volatility, fundamental, leverage, and institutional filter contract.
- Missing required factors exclude a candidate instead of being treated as zero.
- Each match lists its passed factors and evidence date.
- Screener definitions and watchlist choices synchronize to user-scoped server storage, with a browser cache as an offline fallback; they contain no broker credentials.

### Personalized planning

- Goal projection with initial capital and monthly contributions.
- Questionnaire-based risk-capacity label with visible score and capacity conflicts.
- Stress, base-assumption, and favourable scenarios.
- Inflation-adjusted target, user-entered tax-drag assumption, shortfall, and required monthly contribution.
- Explicit separation of arithmetic assumptions from forecasts or tax advice.

## API surface

- `POST /api/v1/intelligence/p2/research/answer`
- `GET /api/v1/intelligence/p2/backtest/{instrument_id}`
- `POST /api/v1/intelligence/p2/screener/evaluate`
- `POST /api/v1/intelligence/p2/planning`

## Data and provider boundaries

- The assistant can only discuss the evidence supplied in its request.
- The UI builds stock evidence from validated daily OHLCV calculations and mutual-fund evidence from stored dated NAV history. Fundamental, valuation, news, ownership, fund-cost, rating, and holdings gaps remain visible until dated provider evidence is connected.
- Advanced fundamental and institutional filters are operational but deliberately produce no matches when those factors are absent.
- AI provider calls remain opt-in, quota-limited, and configured through local environment variables. When unavailable, ATLAS returns an evidence-only synthesis rather than pretending a model ran.
- Screeners and watchlists are isolated by authenticated user on the server. The local cache is only a resilience fallback.
- Tax drag is a user assumption, not a jurisdiction-specific tax calculation.

## Safety statement

P2 produces research explanations, historical evaluations, filter matches, and planning scenarios. It does not predict a guaranteed return, issue regulated personalized advice, place orders, or activate automated trading.
