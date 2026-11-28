# ATLAS multi-strategy research and acceptance

## Research lanes
The analyst consumes the existing completed-session discovery universe and one exact ISIN per company. The primary list preserves strict joint FIP priority while exposing independent alternatives; full strict FIP shortlist/export is unchanged. Price signals require a calendar-matched adjusted suffix. Company financial proxies use current authorized cached reports, exact comparable annual/quarterly periods, minimum AMFI average market capitalization ₹1,000 crore and median daily traded value ₹5 crore. Special securities and known cautions are excluded. Raw price data is not used to qualify price signals. Correlated momentum checks are a single family; sector/regime prioritization is descriptive, not calibrated.

- Advanced FIP uses existing four-window implementation.
- Relative strength uses matched 60-session index dates. Risk-adjusted momentum is a sampled six-month-ex-recent-month quartile proxy; the 12-month observation is retained when available.
- Trend, 52-week high and contraction proxy use causal price windows. The latter is not canonical VCP/SEPA.
- Quality proxy uses matched revenue, profit, operating profit and cash evidence; quality value adds undated reported relative P/E and P/B (not intrinsic value).
- Piotroski partial uses four observed profitability/cash checks; never presents a nine-point score.
- Earnings acceleration uses same-quarter year-over-year and prior-quarter year-over-year acceleration. No PEAD without timestamped surprise.
- Sector momentum uses existing matched official sector index. Low volatility uses matched-date adjusted sample quartiles, not whole-market rank.
- Growth leadership proxy combines acceleration and annual-high evidence. Full CAN SLIM/SEPA/VCP, full QMJ and full Piotroski remain explicitly unavailable until required inputs exist.

## Validation
Reuse the existing rotating replay worker, source/adjustment, listing, revision, action and calendar guards, and current local historical API (up to 500 observations). Four price rules use fixed 60% initial context, chronological holdout, independent 63-session test windows, next-session open/20-session close, nonoverlapping positions, 15/30/60 bps per-side sensitivity. Record daily marked equity net return, drawdown, zero-RF Sharpe/Sortino, CAGR only when at least a year, win rate and profit factor where defined. Matched Nifty 50 price-index comparisons and regime cohorts are descriptive; four or more nonconstant fold returns are needed for pairwise correlation. No portfolio aggregation or claim of total-return alpha.

Paper tracking freezes at most three adjusted company leads per scheduler pass with a 67-day per-company cooldown in the existing immutable watch ledger. Mature outcomes use the existing 60-calendar-day close-to-close observation path, action and calendar checks, and matched price-index comparisons. No simulated executions are represented as fills.

## Release blockers
Actual populated results, independent 5–10 year adjusted histories, historical constituent/delisted coverage, point-in-time financial and expectation data, verified total-return benchmarks, actual costs and portfolio-level walk-forward, independent factor incremental predictive value, and mature paper evidence are not supplied by this change. No qualification gate is lifted. All thresholds/weights are engineering starting assumptions, not backtested optimum. Validate these explicitly before using strategy results as certified buy/sell decisions.

## Local result acceptance
Run after CI and your existing protected local deployment:

```bash
python3 scripts/local_research_acceptance.py --investment-analyst-audit --require-analyst-results --require-multi-strategy-results
```
This requires actual company research across at least two strategy families, current stock/fund decisions, a model review, historical replay companies and frozen paper publications. It is deliberately not strategy certification. A weekend can use the last completed session; do not request live-feed acceptance outside a trading session.
