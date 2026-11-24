# P0–P3 completion audit

Updated: 2026-11-24

This report distinguishes repository capability from provider activation and production approval. A feature is not marked live merely because an adapter or test exists. No real market-data import was performed during this change because no credential, entitlement, or source artifact was read or transmitted.

## Status vocabulary

- **Implemented and tested**: code-owned scope exists with automated evidence.
- **Implemented; activation required**: adapter/workflow exists, but real use needs an authorized credential or source.
- **Partial; external data required**: the product correctly exposes the gap and does not fabricate it.
- **Operator approval required**: infrastructure, legal, security, or recovery evidence cannot be created truthfully in source code.

## Milestone matrix

| # | Scope | Status | Repository evidence | Remaining activation/blocker |
|---|---|---|---|---|
| 1 | Authorized Upstox market data | Implemented; activation required | Instrument master/search, explicit mappings, quote cache/SSE, historical OHLCV validation, freshness, ingestion runs and quality events; database integration tests | An unexpired user-authorized Upstox token and applicable entitlements. A real-account smoke run is still required. |
| 2 | Mutual-fund data | Implemented for public daily NAV; partial for research metadata | Scheduled AMFI refresh, scheme search, dated NAV history/performance/risk calculations, freshness and manual fallback | Verified ratings, TER, riskometer, benchmark and periodic holdings require dated official/licensed disclosures. NAV is daily, not live. |
| 3 | Data reliability/ingestion | Implemented and tested | Versioned Flyway migrations, schedulers/retries, idempotency, calendars, corporate-action provenance, ingestion audit and quality events | Source-specific correction SLAs and corporate-action artifacts must come from authorized providers. |
| 4 | Authentication/security | Implemented for local application boundary | Registration/login, HttpOnly Strict cookie, JWT, same-origin mutation filter, user-scoped holdings/research/history, encrypted versioned broker vault, production Nginx auth gate, secret-safe configuration, dependency review and CodeQL workflow | Independent security review, production secret manager, TLS, rate-limit policy and legacy-owner migration approval. |
| 5 | End-to-end stability | Implemented automated baseline | React, Spring/Testcontainers, Python, operations and production gateway checks run in CI | Real authorized-data smoke and production soak remain environment-dependent. |
| 6 | Fundamentals/valuation | Implemented where provider evidence exists; partial fair value | Statements, earnings, ratios, sector comparisons and dated provider evidence with independent failure states | A defensible fair-value model needs forecast assumptions, point-in-time inputs and approved methodology. |
| 7 | Advanced fund intelligence | Partial; external data required | Historical return, volatility/drawdown, risk-adjusted calculations, comparisons, reconciliation, goal/risk views | Official benchmark, TER, holdings overlap, category/rating and portfolio composition feeds are not licensed/configured. |
| 8 | Institutional intelligence | Implemented for supplied verified evidence; partial feeds | FII/DII flows, shareholding trends and provenance validation | Authorized bulk/block, promoter transaction and ownership feeds. |
| 9 | News/events | Implemented for authorized imports; activation required | Cited news/corporate-event models, dedupe, freshness, source health and corporate actions | No licensed continuous news/IPO feed is configured. Sentiment remains unavailable unless evaluated and audited. |
| 10 | Portfolio intelligence | Implemented and tested | Valuation, allocation, concentration, stress, diversification, rebalancing arithmetic, user cash-flow ledger, valuation snapshots, XIRR and drawdown | Historical metrics require the user to record/import truthful dated flows and valuations. |
| 11 | Smart alerts | Implemented for in-app price/NAV rules | User-scoped rules/history, scheduled local evaluation, daily dedupe, read state and UI | Email/push providers and licensed news triggers are not configured. |
| 12 | Grounded AI research | Implemented and tested | Natural-language evidence packs, strict schemas, citations, uncertainty, comparisons, provider budgets and evidence-only fallback | Each cloud model needs its own valid key/quota. AI output is not verified investment advice. |
| 13 | Prediction/backtesting | Implemented research evaluation | Walk-forward chronology, leakage controls, calibration, benchmark/cost comparison and fail-closed data checks | Production model governance/drift evidence requires real authorized history and an approved model. |
| 14 | Advanced screening | Implemented and user-persisted | Combined filters, missing-factor exclusion, server-side saved screeners and watchlists with offline browser fallback | Results remain empty when required licensed factors are absent. |
| 15 | Investment planning | Implemented scenario arithmetic | Goals, SIP/step-up, risk capacity, stress scenarios, inflation and user-entered tax drag | Not jurisdiction-specific tax advice; assumptions require user review. |
| 16 | Production operations | Repository contract implemented; operator approval required | Immutable images, CI release, SBOM/provenance, loopback gateway, health checks, backups/verifier, restore runbook and bounded load tool | Host/DNS/TLS, secret manager, monitoring receiver, encrypted off-host backup, restore drill and capacity approval. |
| 17 | UX/accessibility | Implemented automated baseline | Responsive layouts, keyboard/ARIA states, onboarding, reduced motion, errors/loading, fixed navigation and persistent tab/appearance | Formal assistive-technology and device acceptance is still an operator QA gate. |
| 18 | Documentation/release readiness | Implemented repository documentation; launch approval required | Architecture, runbooks, user/legal/security/DR docs and this acceptance matrix | Named engineering, security, operations and legal approvers must sign the launch record. |

## Verification commands

```bash
cd frontend/trading-dashboard && npm test -- --run && npm run build
docker run --rm -v "$PWD/backend/trading-core:/workspace" -w /workspace \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e TESTCONTAINERS_HOST_OVERRIDE=host.docker.internal \
  maven:3.9-eclipse-temurin-21 mvn clean -Dtest='*Test,!AiBridgeHttpIntegrationTest' test
docker run --rm -v "$PWD/intelligence:/app" -w /app atlas-intelligence:latest \
  python -m unittest discover -s tests -v
python3 -m unittest tests.test_p3_operations -v
```

## Truthful release conclusion

The code-owned foundation is implemented and tested. ATLAS is **not automatically production-ready** and is **not fully data-complete** until the external activation and approval items above are satisfied. In particular, the repository cannot create market-data rights, refresh an expired broker token, invent missing mutual-fund disclosures, provision an unknown production account, or grant legal approval.

