# Multi-broker research comparison — initial implementation

ATLAS now treats Groww, Zerodha, Upstox, Angel One, ICICI Direct, HDFC Securities, Motilal Oswal, Sharekhan, Kotak Securities, Axis Securities, SBI Securities, Nuvama, JM Financial, Dhan, FYERS and other attributed research providers as **research sources**, not merely trading accounts.

## Scope

- `GET /api/v1/intelligence/research/brokers/sources` lists supported provider labels.
- `POST /api/v1/intelligence/research/brokers/compare` accepts an instrument identifier, evaluation date, report age threshold and up to 300 dated reports.
- Every report must include a provider code, stable instrument identifier, symbol, publication date, normalized rating (BUY, ACCUMULATE, HOLD, REDUCE, SELL or NOT_RATED), title, report ID and HTTPS source URL. Target price and horizon are optional.
- Older reports from the same provider and analyst are superseded; stale reports are excluded from fresh ratings. The API shows firm count separately from report count.
- The output includes per-provider attribution, ratings, median/min/max targets and explicit quality blockers. Empty input produces **no consensus**, not fabricated opinions.
- The dashboard offers an on-demand comparison panel beside market intelligence research views.

## Critical limitations

This release **does not scrape or automatically collect broker reports**. Inputs are user-submitted and **not authenticated as genuine broker research**. A report URL is an attribution reference, not a verification result. No broker's research is represented as available unless actually supplied. Firm/analyst opinions are correlated; simple counts and target medians are not statistically independent, calibrated predictions or buy/sell advice. There is no historical accuracy scoring, research-content extraction, fundamentals verification, live prices or automated trading.

## Next architecture

Build permissioned report ingestion adapters per provider; record report publication and retrieval times, source rights, document hashes, analyst identity and revisions; extract claims with traceable page references; compare earnings assumptions and target methodologies; evaluate historical forecast calibration with survivorship/lookahead safeguards; then combine research as one input to a strict independent decision gate.

Tests: `cd intelligence && python3 -m unittest discover -s tests -v` and `cd frontend/trading-dashboard && npm test && npm run build`.


## Source manifest audit (this batch)

`POST /api/v1/intelligence/research/brokers/ingestion-review` accepts up to 100 user-supplied metadata manifests with provider code, acquisition mode, access and redistribution declarations, report/document ID, publication/retrieval dates, HTTPS provenance URL and SHA-256 declaration. It flags duplicate document IDs, unconfirmed permissions and unverified automated connectors. **Every document remains quarantined** because no report is downloaded, independently hashed, parsed or authenticated. The dashboard has a separate on-demand source audit panel. This is a provenance review, not a licensed feed integration.
