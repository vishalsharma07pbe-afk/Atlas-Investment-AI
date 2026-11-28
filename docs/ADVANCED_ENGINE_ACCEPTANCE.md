# Advanced investment engine: master acceptance checklist

Baseline: merged PR #306, main bcfc746e927b398c281b04e69adb707f154bd7c4. This checklist tracks the six-module development handoff; it is not a claim of release certification. Retain existing protected local deployment, exact-ISIN research, read-only data access, free/included-only provider policy and no broker execution.

Status terms: **implemented** means code exists, **CI verified** means exact-head checks pass, **live verified** requires actual protected local data and provider results, **validated** requires independent investment-performance evidence. None implies the next.

## 1. Multi-strategy engine

- [x] Existing strict FIP and export preserved.
- [x] Adjusted matched-window sample momentum ranks and known recent jump/annual extension exclusion in independent opportunity list.
- [x] Strategy-specific risk geometry and Investment Analyst presentation; conservative Turtle cash/risk helper (not connected to owner allocation).
- [x] Current-session and regime freshness checks; old replay policy results excluded.
- [ ] Independently documented full QMJ factors, point-in-time cross-sectional inputs and validation.
- [ ] Complete CAN SLIM evidence, SEPA beyond trend template, objective VCP/Stage 2 rules and coverage.
- [ ] Turtle portfolio simulation, pyramiding, position allocation, causal channel and stop replay.
- [ ] Automatic authorized pre-announcement earnings expectations and independently verified actual results for PEAD.
- [ ] Piotroski exact component source coverage; no imputed inputs.
- [ ] Cross-sectional and sector comparisons, validated performance-based weights, correlation and incremental contribution.
- [ ] End-to-end evidence for at most ten distinct, supported stock opportunities. Do not fill empty lists artificially.

## 2. Autonomous multi-AI research

- [ ] Actual authorized ChatGPT plan, Gemini, Ollama and Groq inference and quota acceptance.
- [ ] Official public source discovery, document extraction, exact identity/date/figure provenance, conflict handling and missing-evidence resolution.
- [ ] Bull/base/bear thesis and counterarguments, independent verification, evidence memory, material-event reassessment and task-aware routing.
- [ ] Verify local privacy, free-only constraints, bounded cache and rate limits. Provider agreement is not evidence.

## 3. Predictive research and valuation

- [ ] Evidence-bound revenue, margin, EPS and cash-flow scenarios; earnings sustainability, catalysts, economic and industry context.
- [ ] Appropriate DCF or sector-specific valuation, comparable peers, bull/base/bear fair value, margin of safety and downside/upside.
- [ ] Risk-adjusted horizon-specific rankings and recommendation invalidation. Distinguish facts, assumptions and forecasts.

## 4. Mutual fund intelligence

- [ ] Official automatic NAV and TER; metadata, manager tenure and track record, style and strategy.
- [ ] Rolling benchmark/risk-adjusted performance, drawdowns/recovery, consistency across regimes.
- [ ] Weighted underlying earnings outlook, exposure/concentration, portfolio overlap, costs, exit loads.
- [ ] Explicit future scenarios, SIP and alternative fund comparison, tax-aware suitability.
- [ ] Selective live large-, mid- and small-cap lists, no unsupported recommendation.

## 5. Portfolio intelligence

- [ ] Holding thesis/action, deterioration, stronger alternatives and opportunity cost.
- [ ] Concentration, sector and underlying fund exposure; recovery and monthly capital planning.
- [ ] Local risk budget/position sizing, stress tests, scenario allocation, tax/cost-aware rebalancing and next moves.
- [ ] Continuous monitoring and invalidation. Never sell solely because of losses or send private holdings externally.

## 6. Independent strategy validation

- [ ] Authorized 5–10 year adjusted histories and point-in-time fundamentals/expectations, historical constituents and delisted securities.
- [ ] Survivorship/look-ahead guards, out-of-sample and portfolio walk-forward, realistic India-specific costs.
- [ ] CAGR, Sharpe, Sortino, drawdown, win rate, profit factor, total-return benchmarks and regime tests.
- [ ] Correlation, incremental predictive value, confidence calibration and portfolio allocation.
- [ ] Immutable prospective results, observed-outcome learning, degradation monitoring. Never certify on registration or proxies.

## Final application acceptance (all pending live verification)

- [ ] Exact-head CI/security and production Docker builds, compatible APIs.
- [ ] Actual authorized AI responses and included/free usage behavior.
- [ ] Actual stock/fund lists, holding decisions, capital plan, refresh and invalidation.
- [ ] TradingView synchronization where authorized, historical and prospective results.
- [ ] Privacy and absence of fabricated data or unsupported claims.

Run after protected local deployment:

```bash
python3 scripts/local_research_acceptance.py --investment-analyst-audit --require-analyst-results --require-multi-strategy-results --qualification-audit --advanced-audit --recovery-audit
```

The existing 500-observation history API and incomplete historical constituent coverage, absence of an automatic authorized PEAD consensus source and insufficient mature prospective evidence remain qualification blockers. Local account authorization and market-data verification cannot be substituted by CI. Update this checklist only against observed evidence.
