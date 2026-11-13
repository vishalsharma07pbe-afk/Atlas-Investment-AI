# Mutual Fund Intelligence — delivery and production-readiness gates

## Implemented in the current research-only module

- Saved mutual fund holdings and manually recorded valuations, with missing-NAV warnings
- Source-attributed AMFI-style snapshot inspection and name/code discovery from user-supplied text
- Strict scheme-code historical CSV validation, NAV returns and historical drawdown/guarded volatility
- Multi-fund historical comparison with date-alignment warnings
- Explicit scheme-code read-only portfolio reconciliation and stale/missing/mixed-date diagnostics
- SIP and goal planning, portfolio concentration diagnostics and NAV refresh preflight
- React integration tests for import to risk, comparison and reconciliation

## Still required before calling this production-complete

1. **Licensed/authorized feed:** choose an authorized NAV source, confirm access rights, rate limits, retention and redistribution terms. No live provider is connected today.
2. **Persisted scheme master:** source-verified scheme code, plan/option identifiers, active/inactive status, change history, explicit holding mapping and migrations.
3. **Ingestion lifecycle:** idempotent scheduled NAV fetch, backfill, raw-source provenance, checkpoints, retries, error queues, refresh observability and reconciliation audit trail.
4. **Historical integrity:** corporate/fund events, dividend and distribution adjustments, missing dates, source revisions, benchmark eligibility and reproducible as-of calculations.
5. **Portfolio valuation:** authoritative unit ledger, purchase/redemption transactions, cost basis, split/merger treatment, verified valuation timestamps, permissions and audit logs.
6. **Fund reference analytics:** expense ratios, categories, holdings/overlap and benchmark comparisons only when independently sourced and licensed.
7. **Operational quality:** integration tests with provider fixtures, authorization/security tests, large-file and concurrency tests, performance budgets, accessibility and deployment/runbook checks.

**Current safety boundary:** All imported snapshots and historical NAVs are user-supplied and unverified. Research calculations are read-only; neither automated trades nor authoritative portfolio updates are enabled. The scheme discovery feature never infers a holding's scheme code.
