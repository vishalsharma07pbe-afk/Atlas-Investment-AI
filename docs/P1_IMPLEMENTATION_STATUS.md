# ATLAS P1 Intelligence — implementation status

Updated: 2026-11-19

ATLAS treats provider observations as evidence, not as automatic investment advice. Missing or unauthorized inputs remain visibly unavailable.

## Operational

- Company profile and sector context by ISIN.
- Consolidated yearly income, balance-sheet, and cash-flow summaries.
- P/E, P/B, ROA, ROE, ROCE, quick ratio, and EV/EBITDA with provider sector comparisons.
- Shareholding history, including promoter, FII, DII, and public categories when supplied.
- Corporate actions and comparable-company discovery.
- Company news with publication timestamps and clickable source citations. Sentiment remains `NOT_ANALYZED` until a tested method and audit trail are added.
- Aggregate FII and DII NSE cash activity at daily or monthly intervals.
- Existing portfolio valuation, allocation, concentration, stress scenarios, and evidence-gated research views.
- Existing mutual-fund discovery and fail-closed ranking methodology.
- Existing on-demand daily price/RSI/volume threshold checks.
- User-scoped external cash-flow ledger and dated portfolio valuation snapshots, with XIRR and maximum-drawdown calculations that stay unavailable until enough history exists.
- User-scoped price/NAV alert rules, scheduled evaluation against stored sourced observations, deduplicated in-app history, and read state.

## Blocked by missing evidence or product infrastructure

- Mutual-fund Sharpe/Sortino, benchmark-relative returns, portfolio overlap, official expense ratios, riskometer, and category rankings need dated NAV history plus official AMC/AMFI/SEBI disclosures. The daily discovery catalog alone is not sufficient.
- Bulk/block deals and promoter transactions need an authorized, documented source and revision policy.
- XIRR and drawdown require truthful user-entered/imported cash flows and multiple dated valuations; current holdings alone still cannot reconstruct history.
- Email/push delivery and licensed news-trigger evaluation require separately configured providers. The implemented channel is in-app delivery.
- Fair value is not derived from a P/E or P/B comparison. A defensible valuation model needs forecast assumptions, point-in-time filing data, and a versioned methodology.

## Provider and safety boundaries

- All new provider calls are read-only.
- Tokens are read from environment configuration and are never returned by an API.
- Each company section fails independently; one unavailable endpoint does not erase other evidence.
- Provider failures, rate limits, invalid identifiers, and schema mismatches fail closed.
- No order endpoints or automated trading paths are used.

## Verification

- Intelligence unit suite: 383 tests passing.
- Frontend suite: see `P0_P3_COMPLETION_AUDIT.md` for the release-branch result.
- Frontend production build: passing.
- Live configured-provider validation: 8/8 company sections, 7 key ratios, FII/DII daily records, and cited recent news returned for the validation instrument.
