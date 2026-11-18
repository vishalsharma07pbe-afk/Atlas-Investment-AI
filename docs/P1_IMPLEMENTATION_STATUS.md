# ATLAS P1 Intelligence — implementation status

Updated: 2026-11-18

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

## Blocked by missing evidence or product infrastructure

- Mutual-fund Sharpe/Sortino, benchmark-relative returns, portfolio overlap, official expense ratios, riskometer, and category rankings need dated NAV history plus official AMC/AMFI/SEBI disclosures. The daily discovery catalog alone is not sufficient.
- Bulk/block deals and promoter transactions need an authorized, documented source and revision policy.
- Portfolio XIRR requires a transaction/cash-flow ledger; current holdings and average costs cannot reconstruct historical cash flows safely.
- Portfolio drawdown requires dated portfolio valuation history, not only the current snapshot.
- Persistent alert rules, background evaluation, delivery channels, preferences, and delivery history need user-scoped storage and a scheduler. Current threshold checks are explicitly on demand.
- Fair value is not derived from a P/E or P/B comparison. A defensible valuation model needs forecast assumptions, point-in-time filing data, and a versioned methodology.

## Provider and safety boundaries

- All new provider calls are read-only.
- Tokens are read from environment configuration and are never returned by an API.
- Each company section fails independently; one unavailable endpoint does not erase other evidence.
- Provider failures, rate limits, invalid identifiers, and schema mismatches fail closed.
- No order endpoints or automated trading paths are used.

## Verification

- Intelligence unit suite: 364 tests passing.
- Frontend suite: 80 tests passing.
- Frontend production build: passing.
- Live configured-provider validation: 8/8 company sections, 7 key ratios, FII/DII daily records, and cited recent news returned for the validation instrument.
