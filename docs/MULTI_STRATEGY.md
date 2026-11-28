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

## Extended professional rule catalog
The catalog now includes Donchian 20-session breakout, Turtle long 55-session breakout (not full Turtle pyramiding/portfolio system), Stage 2 five-session-sampled trend proxy, SEPA trend template, objective VCP contraction, mean reversion, Wyckoff accumulation proxy, daily typical-price anchored VWAP reclaim, historical-profit-growth GARP proxy, CAN SLIM growth/leadership proxy, matched 60-session beta, and complete nine-component Piotroski evaluator when exact annual inputs exist. QMJ-style ranks use a simplified four-dimension same-sector/same-period cohort, not exact replication of AQR's factor. All 12 price rules enter the existing replay worker. Reversal is experimental and has its own family, not evidence of independent returns. All rules remain nonqualified until independent validation; fixed 20-session replay exits are not canonical exits for Turtle or other discretionary strategies.

PEAD is integrated behind an optional local authorized event input `data/filing-reports/earnings-expectations.json` (disabled by default; no feed is supplied). A separately reviewed normalized input requires `methodology: AUTHORIZED-EARNINGS-EVENTS-1`, events with exact ISIN, quarter_end, consensus_eps, actual_eps, consensus_as_of, released_at (offset timestamps), analyst_count >=3, same_share_basis, consensus_verified, release_verified, operator_reviewed booleans, separate HTTPS consensus_source/release_source and corresponding document SHA256 fields. The input is an operator-attested observation, not source verification by ATLAS. Never generate consensus from AI or substitute historic growth. The release must precede the completed stock observation. No automatic paid source or external request is added. A real authorized source and independent validation remain necessary. Do not enable on fabricated inputs.

The event feed's provenance attestations are operator-reviewed, not independently fetched or verified by the application. Source documents and their digests must be independently verified before enabling the import. The acceptance contract never treats the presence of an imported PEAD event as strategy qualification.

## Strategy-specific risk geometry (advanced engine, module 1)

Adjusted, calendar-matched completed-session observations expose illustrative risk plans to the Investment Analyst for Turtle 55-session, Donchian 20-session, mean reversion and selected trend rules. Wilder 20-session N includes price gaps. Turtle uses the prior 55-session high, 2N initial stop and 20-session channel exit; 0.5N spacing is descriptive only. The two-R comparison target is not a Turtle profit-taking rule. Donchian uses a 10-session channel/2ATR stop; mean reversion uses the prior 20-session mean; trend rules use recent support/2ATR. Raw, inconsistent, excessively volatile or invalid geometry cannot produce a plan. No plan is a fair-value estimate or broker action.

A cash-only conservative Turtle sizing helper caps a hypothetical initial 2N loss at at most 1% of supplied capital and respects available cash. It is not canonical 1N sizing, is not yet connected to owner allocation, and does not simulate pyramiding or portfolio risk. Existing fixed-hold replay rules are unchanged and cannot validate these new exits. Full Turtle portfolio validation remains pending.
