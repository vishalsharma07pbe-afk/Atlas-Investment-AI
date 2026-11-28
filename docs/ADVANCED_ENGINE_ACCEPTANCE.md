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

## Integrated implementation in PR #307 (code-level only)

The six workstreams are advanced together, not marked complete independently.

| Module | Implemented in consolidated branch | Still required for full acceptance |
|---|---|---|
| 1 | Strategy-specific price risk geometry; exact-date momentum cohort; pump guard; visible Piotroski component and trend/contraction diagnostics | Complete canonical financial/ownership/expectation coverage, actual independent opportunity output, full portfolio risk/pyramiding |
| 2 | Ordered role-specific reviewer routing, actual provider IDs, bounded anonymous official-document retrieval, content digests and HTML exact identity mentions; conditional evidence thesis | Authorized live responses, independently verified dated financial extraction, contradiction resolution across documents, source completeness |
| 3 | Reuse frozen quarterly persistence on alternate stocks, explicit ±10 percentage point bear/base/bull revenue and profit amounts and margins, existing cash sensitivity projection | Actual forecasts, verified capex/FCF, share basis, EPS, sector-appropriate fair value, calibration |
| 4 | Exact-scheme, dated TER evidence and conflict withholding in analyst cards; historical drawdown and volatility | Live authorized TER mapping across all categories, manager/mandate/exit-load/portfolio/tax evidence and verified fund growth qualification |
| 5 | Owner-local asset-class stress scenarios, concentration diagnostics and 0.5% fresh-capital stop-risk cap in existing planner | Full owner evidence, underlying fund exposure, portfolio rebalancing and actual tax/cost calculations |
| 6 | Causal next-open single-instrument channel/stop experiment, retained gap losses, cache refresh and aggregate observations | Full portfolio walk-forward, point-in-time universe, long adjusted history, total-return benchmark, mature paper outcomes |

Use the existing acceptance command with the additional option `--require-advanced-engine-results`. This reports actual stock thesis/price/quarterly scenario counts, matching TER in all three categories, four actual provider review IDs, official-document retrieval receipt, channel experiments and owner-local stress observation. It returns nonzero if any expected integrated output is missing. It deliberately cannot certify the canonical strategies or real investment performance. An empty portfolio is explicitly not applicable for stress testing.

Current fixed shocks, quarterly shifts and risk caps are illustrative engineering assumptions. All external document retrieval is permission-gated and bounded; retrieval does not prove a document's claims. Do not enable extra subscriptions or send private holdings to external providers.

## Additional code implemented after the integrated first pass

- Shared-capital, exact-session audited cohort channel replay: cash constraints, up to four units per company, close-confirmed next-open pyramiding and exits, capital/risk caps, measured drawdown and risk ratios. No historical constituent membership, no canonical intraday stop execution, no total-return comparison, no certification.
- Conditional source-bound FCFF/FCFE/dividend discount valuation, including per-share scenario values, price-relative upside/downside, margin-of-safety arithmetic and conditional EPS when supplied. It is opt-in and requires operator-reviewed exact cash/share/price inputs and source files matching SHA-256 digests; it is not autonomous acquisition or authentication.
- AI committee receives a bounded allowlist of conditional value, TER and matched TRI evidence; adverse fund fee conflicts cannot be overridden by model prioritization. Source document text and owner data are not sent.
- Fund recommendation cards show existing matched benchmark evidence, dated reported managers/exit terms and underlying business growth sensitivities. A conflicting TER defers allocation.
- Local capital planner uses existing portfolio-level attention and the existing funding, FIFO/exit-load/conditional tax comparison pipeline. Fund acquisition-specific tax treatment remains withheld when unsupported.
- Regression tests were added. No new paid provider or broker action is introduced.

The checklist above remains authoritative; these changes do not make all six modules fully complete. Source-bound valuation needs authorized evidence files, while automatic PEAD consensus, complete canonical factor and institutional ownership inputs, independent extraction of actual filing figures, verified fund manager tenure, long point-in-time market histories and prospective maturity remain unresolved. Exact-head CI and protected local live acceptance are required.

### Source-bound valuation input contract

Use only authorized public documents in the existing `data/filing-reports` read-only mount. Enable `ATLAS_VALUATION_EVIDENCE_ENABLED=true` only when market-data usage rights are confirmed. The optional `valuation-evidence.json` document requires methodology `SOURCE-BOUND-VALUATION-1`, `authorization_attested: true`, and a `companies` array. Each exact ISIN record contains:

- `operator_reviewed: true`, `scope: CONSOLIDATED_INR_CRORE`, fiscal period end, review date, price date, actual unadjusted INR reference price, diluted shares in crore, same-share-basis attestation.
- `model: FCFF` for nonfinancial companies: EBIT, depreciation, explicit capex, signed working-capital increase, tax rate assumption and net debt (crore). `FCFE`: operating cash, capex and net borrowing (crore). `DIVIDEND_DISCOUNT` for financial companies: annual dividends (crore). Select the corresponding sector type.
- Exactly three ordered BEAR/BASE/BULL scenarios with explicit growth, discount and terminal growth percentages, and optional next-year net profit amount (crore). No inferred values or default assumptions.
- Three distinct source files in the same mount, roles FINANCIAL_STATEMENTS, SHARE_AND_PRICE_BASIS and VALUATION_ASSUMPTIONS, each with file name and actual SHA-256. Files and total read budget are bounded. No arbitrary URL or local path is fetched. Do not insert credentials, private documents or synthetic test data.

The strict integrated acceptance flag now additionally requires at least one source-bound stock valuation, matched TRI evidence in all three core fund categories, and a shared-cash replay of at least two exact-session companies. It does not require manufacturing a result in an unfavorable market or bypassing evidence checks. Full independent certification remains separate.

## Final decision quality and effectiveness policy

The final analyst projection now evaluates evidence readiness after attaching the independently cached AI reviews. Priority research requires all stated research checks; missing evidence is a watch rather than a negative factual assertion, and adverse evidence is never outweighed by a high preliminary score or an AI vote. Existing canonical qualification and TradingView exports remain separate. No fixed count is forced. The stock/fund lists remain separate and original screening scores are not added across incompatible methodologies. The owner-local capital planner uses the final policy when present.

The scheduled mutual fund snapshot now persists a compact exact-identity decision context and the already observed peer risk metrics. It no longer drops all TER/benchmark evidence before the Investment Analyst. Read-time source permissions and age gates are reapplied, and raw reports/holdings/source URLs are not copied. Refresh the underlying fund sections before expecting the new fields.

A new versioned cohort in the existing watch ledger freezes actual adjusted joint-screen stock decisions, at most one per decision state per IST day with an exact-ISIN overlap guard. It uses the existing audited 60-calendar-day outcome evaluator; no historical backfill. Reports show mature denominators, observed coverage, net price changes at illustrative 30 bps per side, and median paired difference against the existing Nifty 50 price index. A priority cohort with at least 30 paired outcomes, 20 companies, 10 publication dates, 80% paired coverage and nonpositive median excess pauses new stock allocations. These fixed caution thresholds are not validated optimal thresholds or statistical significance. No positive sample establishes calibrated alpha; no automatic strategy weight promotion. The existing fund historical peer ledger now freezes the exact final decision state at original publication when a current matching analyst decision is available. Prior rows are never backfilled. The dashboard reports 90-day official NAV outcomes separately by category and decision state; no benchmark-adjusted or tax-adjusted inference or fund allocation pause follows from those raw NAV returns. Full independent investment-performance validation still requires point-in-time historical universe, longer history, TRI and actual prospective maturity.

Strict integrated live acceptance also checks final decision-state counts, versioned row contracts, and absence of positive allocation actions on incomplete or adverse rows. It does not require a nonempty priority list or a positive investment outcome merely to pass the software contract.

## Predictive, adaptive and outcome-based research improvements

- The existing immutable quarterly earnings ledger now freezes fixed half-persistence and damped-acceleration challengers where exact positive anchors support them. It evaluates matched errors versus persistence and unchanged seasonal baselines, never retrospectively adding models to old records. Multiple mature quarters are required for a model review; weak persistence evidence pauses dependent new allocations. These are uncalibrated experiments, not earnings forecasts or consensus.
- Multi-strategy publications freeze the same-session market regime. Separate 60-day publication windows, separated sufficiently to avoid overlap between their outcome windows, require at least 20 paired exact companies, ten dates and 80% coverage per window. A weak recent sample reduces priority; positive median net index excess in both windows adds descriptive priority, not a validated allocation weight. Cost is an illustrative 30 bps per side. The original FIP qualification and exports are unchanged.
- The final analyst uses exact current NSE filing/provider reconciliation acquired by the existing official-index/manifest worker. Arithmetic agreement is not audit certification; disagreement is adverse evidence. Automatic official filing acquisition still requires supported NSE format, consent and actual endpoint access; PDF and other issuer formats remain unsupported by this specific parser.
- Local new-capital planning uses whole-share stock sizing, 0.5% per-position and 0.75% combined hypothetical stop-risk caps, an illustrative 30 bps purchase-cost reserve, duplicate exclusion and same-date/category/benchmark fund dominance on reported expense, historical excess and downside metrics. The fixed thresholds are engineering assumptions, not optimized or statistically validated parameters. No sales or realized taxes are inferred; existing sale and exit-load research remains separate.
- Fund publications can freeze a matching category gross TRI proxy. Exact official NAV endpoints are paired with available authorized TRI endpoints at maturity without interpolation; missing observations remain missing. A sufficiently covered adverse category cohort pauses new SIP research allocations. The proxy is not a historical fund mandate, and NAV returns are not tax-adjusted. No TER is subtracted a second time.
- Full production CI, authorized real-data acquisition, long point-in-time history, adjusted total-return benchmarks for stock strategy validation, calibrated prediction, and actual prospective outcomes remain required. No numerical performance improvement is asserted without those observations.
