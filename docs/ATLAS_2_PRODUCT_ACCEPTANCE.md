# ATLAS 2.0 product acceptance
The operator's ATLAS 2.0 specification (24 November 2026) is the governing goal, not the count of PRs. Reuse the existing repository; the normal workflow is opening the dashboard, reading the briefing, monitoring holdings, reviewing automatically researched opportunities and funds, and opening a complete report when needed. Initial authorization, preferences and holdings setup are permitted. Data imports and diagnostics are administrative fallbacks. Never execute orders, automate broker authorization, require bank connections, invent evidence, or disclose private holdings to external AI. Keep local Docker/Apple Silicon as the primary target.

## Traceability against the 18 original priorities
This is a source-level gap record, not a real-data acceptance certificate. Existing implementation and automated test infrastructure are not proof of complete workflows. PR #154 passed the eight ATLAS checks and security scans; new changes require their own CI. Actual authorized data, populated portfolio, and local resource/UX acceptance remain unverified.

| Priority | Existing implementation to retain | Product acceptance still required |
|---|---|---|
| 1 Market data | Upstox V3, registry, history, streams, discovery batch reads, recovery | Authorized OAuth/reconnect, reliable holdings sync and data, exact identities, verified calendar/actions, same-market authorized fallback and coverage |
| 2 Mutual funds | AMFI NAV, history, peer risk research, strict fund ranker | Dated official category/plan, TRI, TER, AUM, manager, riskometer, portfolio disclosures and forward evidence integrated into automatically qualified rankings |
| 3 Ingestion | Existing schedules, claim ledgers, quality events, snapshots | Dependency-aware orchestration, persistent job state, restart recovery, IST schedule and priority for holdings/events, publication-aware refresh |
| 4 Security | JWT, cookie checks, vault, local-first AI | Real local isolation, reconnect workflow, credential handling and security verification |
| 5 Stability | CI and HTTP/browser integration, local acceptance command | Populated-data regression, upgrades, representative resource/load/soak and outage tests |
| 6 Fundamental research | Cached company reports and annual trends | Independently dated fundamental evidence, leadership, peers, valuation ranges with assumptions, complete report |
| 7 Fund research | Category historical watch and strict ranking | Comparable risk-adjusted metrics, consistency, benchmark/fees, holdings overlap and future research from portfolio quality; additional fund categories |
| 8 Institutional | Automatic aggregate FII/DII and shareholding evidence | Authorized stock-level ownership, bulk/block, promoter/pledge, breadth and regime, derivatives where permitted |
| 9 News | Automatic watched-company news with dates, topics and sources | Global/macro/events, corporate calendar, relevance, materiality and validated sentiment; cited filings where permitted |
| 10 Portfolio | Owner-scoped review, thesis, risks, correlation, opportunity context | Same-depth holding reports, actual cash-flow history, benchmark, thesis-change monitoring, fund look-through, verified scenarios |
| 11 Alerts | In-app price/NAV, risk and news alerts | Automatic opportunity/thesis/event/provider notifications with severity, cooldown, dedupe and affected research; optional delivery |
| 12 AI | Existing typed multi-provider review, quota gates and local private analysis | Role-based committee across evidence domains, disagreement and evidence validation, bounded and sanitized inputs |
| 13 Evaluation | Fixed-rule replay, prospective immutable watch ledger | Adjusted point-in-time history, realistic execution/costs, benchmark/regime, out-of-sample and immutable qualified-result outcomes |
| 14 Screening | Bounded automatic daily and intraday technical watches | Integrated decision qualification/ranking per four horizons, up to five qualified reports, deterministic conditional levels, actual coverage |
| 15 Planning | Scenario and goal arithmetic | Verified assumptions, relevant taxes and portfolio alternatives, not automatic investment instructions |
| 16 Operations | Compose, backup verifier, recovery and deployment tests | Reliable actual local upgrades and recovery, resource budget, release safeguards, authorized local acceptance |
| 17 UX | Existing result-first workspaces, overview and portfolio digest | Concise briefing, market regime, attention items, complete click-through reports, isolated diagnostics, populated desktop/tablet/mobile acceptance |
| 18 Release | Runbooks, endpoint compatibility, acceptance script | Dated traceable end-to-end acceptance for all priorities, external blockers, exact release CI and actual local verification |

## Integrated daily briefing
The existing overview endpoint includes a deterministic summary of current saved research only. Stale/failed/disabled sections do not count as current. Equity watch counts are not qualified recommendations; full qualification remains unavailable. Fund growth picks are distinct from historical watches and pending categories. Institutional directions use existing paired five-date evidence, not a forecast. No new external call, private holding payload, or separate scheduler. The existing portfolio summary and detailed research views remain in place. This is a partial vertical improvement to Phase E, not a completed AI briefing or final recommendation engine. The next substantive work must connect dated stock/fund/portfolio evidence to actual qualification and complete reports, and continue Phase B source reliability where it blocks them.

## Release decision
Require all applicable original acceptance criteria: actual automatic data refresh and portfolio monitoring, autonomous stock/fund discovery, grounded AI, meaningful conclusions and reassessment conditions, automatic alerts, truthful failures, clean result-first UI, privacy, restart stability, green exact-release CI, independent authorized-data acceptance, no trade execution, and documented evidence/blockers. Do not claim production completeness from a passing synthetic run. Do not delete existing volumes. Review and complete related work as cohesive vertical phases.
