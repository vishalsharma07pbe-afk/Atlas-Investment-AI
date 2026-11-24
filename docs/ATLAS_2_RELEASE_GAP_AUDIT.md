# ATLAS 2.0 release-gap audit

Baseline: be2582e8b0b682ed25147b6f6898f04fc4282a0b. PRs 120–128 merged; their required checks passed, including the retried Spring-to-Python workflow for #128. This is a source-level review, not a local deployment or a production approval. No credentials or real account records were accessed.

| Priority | Repository capability | Remaining release gate |
|---|---|---|
| P0 market data | Existing Upstox master/history/quote adapters, bounded automatic history and portfolio prices | Confirm authorized live access, broader liquid universe, adjusted series and current-session evidence |
| P0 mutual funds | AMFI daily NAV, MFAPI history, category-wise performance watch | Official TER, benchmark, riskometer, holdings, rating provenance; future qualification |
| P0 ingestion | Persistent schedules, dedupe, retries, quality checks | Calendar completeness, corporate actions, outage/soak tests |
| P0 security | User isolation, encrypted token vault, provider permissions, local-first AI | Independent security review, token lifecycle and real deployment verification |
| P0 stability | CI baseline through #128 | Run exact new release CI, authorized local smoke and migration checks |
| P1 fundamentals | Existing company report adapter | Automatic point-in-time fundamentals, peers and valuation enrichment of candidates |
| P1 fund research | Historical comparison and strict gates | Risk-adjusted benchmark/fees/overlap and growth evidence |
| P1 institutions | Provider/report and local ledger tools | Continuous authorized flows, bulk/block, ownership and promoter evidence |
| P1 news | Local attributed imports and existing provider endpoints | Continuous licensed ingestion, dedupe, event risk, validated sentiment |
| P1 portfolio | Automatic prices and basic holding review | Thesis-level fundamentals/news/AI review and verified cashflow history |
| P1 alerts | Owner-scoped daily risk digest and saved price/NAV rules | Opportunity change alerts, freshness-gated price rules, external channels if explicitly enabled |
| P2 AI | Bounded automatic cited public technical commentary | Full evidence enrichment, independent factual review, fund/holding research; no calibrated confidence |
| P2 backtesting | Historical tools and forward observation ledger | Mature adjusted observations, realistic costs/benchmarks, walk-forward strategy validation |
| P2 screening | Bounded sample and distinct technical horizons | Genuine intraday screening, whole eligible market coverage, joined verified fundamentals |
| P2 planning | Existing scenario/goal tools | User-approved assumptions and tax rules; no automatic financial advice |
| P3 operations | Compose, release and recovery runbooks | Actual local performance, backups/restore drill, production approval if required |
| P3 UX | Dedicated overview/portfolio/research/settings, deferred tools | Browser/device/accessibility acceptance, click-through detailed evidence reports |
| P3 release docs | Existing checklists and this audit | Exact release record with all remaining gates evidenced |

## Correction in this change

Settings previously described automation as disabled or blocked unconditionally and the backend always said MANUAL_CSV_ONLY. The backend now reports actual stored registry, official AMFI NAV and validated completed Upstox daily evidence, separately from live transport. Python reports configured research scheduling, current snapshot states and only calls a live feed verified when a subscribed tick meets the existing cache freshness rules and permissions. Source summaries use preaggregated counts instead of multiplying every instrument by every candle within a source. Legacy local catalogs remain separately labeled. No claim of production readiness or complete recommendations is enabled by the change.

## Release decision

Not release-ready for the original autonomous research objective. Next code-owned blockers: automatic company evidence enrichment, verified current-session research, official fund metadata/risk evidence, fresh price alert gates and outcome validation. Data rights, authorized credentials and local acceptance cannot be manufactured in CI. Existing launch acceptance checklist remains binding for public/multi-user launch. No live provider or real-account validation was performed during this audit.
