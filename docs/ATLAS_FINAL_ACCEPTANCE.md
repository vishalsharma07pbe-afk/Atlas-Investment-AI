# ATLAS 2.0 final acceptance matrix — 2026-11-26

Baseline: PR #263 merged at `832f6f4a328eea0f17151658fd22fb0593a83a23`; corrected head passed eight application jobs and four applicable security jobs. Full OSV scan skipped. This record is an engineering handoff, not a certificate that all requested product functionality is complete. Current PR requires its own green CI.

| Original priority | Implemented foundation / traceability | Remaining acceptance or implementation |
|---|---|---|
| 1 Market data | Authorized Upstox registry, daily history and live read adapters, B workstream | Actual account authorization, freshness and reconnect; full same-market authorized fallback and coverage not certified |
| 2 Mutual fund data | AMFI NAV/history and metadata ingestion, D workstream | Complete comparable official TER/AUM/manager/riskometer/benchmark/disclosure coverage |
| 3 Ingestion | Persistent scheduler and source-specific gates, L01–L03 | Real-day schedule, outages, catch-up and source completeness on operator device |
| 4 Security | JWT, vault, private AI boundary, #260–262 | Local keys/permissions, two-account real deployment and explicit legacy notes migration if needed |
| 5 Stability | CI, HTTP, browser, recovery, bounded reads #258–259 | Actual populated stack soak, CPU/RAM, outage and restart measurement |
| 6 Fundamental research | Dated company evidence, peers and conclusion C/I | Independently verified full fundamentals, leadership, valuation and coverage |
| 7 Fund research | Category history and strict growth qualification D | Actual eligible funds, comparable net performance, risk, forward evidence and source completeness |
| 8 Institutional research | Aggregate flow, shareholding and authorized deal ingestion F | Actual dated stock-level ownership, bulk/block and derivative evidence as authorized |
| 9 News and events | Company news, releases, economic calendar and macro F | Live authorized source coverage, dated relevance and sentiment verification |
| 10 Portfolio | Owner-scoped holdings/thesis/risk, look-through and planning E | Verify actual holdings, transactions, valuation, exposure and recommendations with real data |
| 11 Alerts | Automatic risk/event history and private alerts K | Verify delivery and deduplication with actual events; no unsupported external delivery claim |
| 12 AI | Local-first public typed committee, quota/claim guards G | Actual enabled-provider health, evidence quality, disagreement and privacy review |
| 13 Strategy validation | Historical replay, cost and regime research H | Representative adjusted point-in-time datasets, out-of-sample validation and calibration; no validated trade outcomes |
| 14 Screening | Canonical technical watch selection I and intraday reads | Certified integrated stock qualification, conditional targets/stops and reliable opportunity rankings remain incomplete; do not relabel watches as recommendations |
| 15 Planning | Owner-local goals, contributions, fees/tax reference and risk E | Actual charges, liquidity, acquisition terms, affordability and suitability evidence |
| 16 Operations | Verified archive, isolated restore and local backup #259/#263 | Prior-version populated Mac upgrade, recovery timing and configuration preservation |
| 17 UX | Result-first overview, exact reports and accessible overlays J | Actual populated desktop/mobile/Safari review and usability acceptance |
| 18 Release | Existing route compatibility, exact-release CI and local acceptance L | Complete these evidence gaps, document exact release, sign off only after verification |

## Operator verification order
1. Verify exact current release CI, retain prior version and protected configuration. Follow local deployment runbook; backup before rebuild. No reset, no volume deletion.
2. Start same local project and sign in. Confirm portfolio records and existing configuration match pre-upgrade state; assign legacy notes only with explicit ownership.
3. Run `python3 scripts/local_research_acceptance.py` on the device. Review only its redacted status output; use --require-live only during an expected authorized live session.
4. Verify actual holdings quantities, cost basis, prices, transactions and dated research against authorized sources; inspect full stock/fund reports, absence of qualified picks and all blockers.
5. Observe scheduler/provider reconnect, history, notification behavior, resource usage and responsive UI. Perform an isolated real-data restore drill; never overwrite live storage.
6. Resolve remaining data/qualification gaps before certifying original product scope. A green contract run can be a valid research-only engineering release, not a fully qualified investment intelligence product.

The local command deliberately prints NOT_CERTIFIED for both investment qualification and overall product acceptance, even when all read contracts pass. Observation markers do not establish accuracy. No broker actions, bank linkage, credential export or automated trade execution are introduced.
