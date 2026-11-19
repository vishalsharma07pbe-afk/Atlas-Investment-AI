# Launch acceptance checklist

A public or multi-user launch is **blocked** until every required item has dated evidence and an accountable approver.

## Engineering

- [ ] CI, production image builds, migration validation, integration tests, and dependency/security review are green for the exact release commit.
- [ ] Image digests, SBOMs, provenance, configuration version, and release notes are retained.
- [ ] Responsive checks cover 320px, 768px, desktop, zoom at 200%, keyboard-only use, reduced motion, dark/light/system themes, and screen-reader landmarks.
- [ ] Load and soak tests use representative authorized data and meet approved latency, error, CPU, memory, and database thresholds.

## Security and privacy

- [ ] TLS, secure cookies, rate limiting, secret manager, least-privilege database roles, network policy, log redaction, vulnerability management, and incident response are independently reviewed.
- [ ] Registration policy, user isolation, deletion/export, retention, consent, vendor processing, and breach-notification procedures are approved.
- [ ] No production secret exists in Git history, images, CI logs, browser bundles, backups, or support tickets.

## Data and model governance

- [ ] Every market/news/fund source has documented rights, provenance, freshness SLA, mapping controls, revision policy, and outage behavior.
- [ ] Corporate-action treatment and adjusted/unadjusted series are explicit.
- [ ] Model prompts, versions, budgets, grounding, evaluation, drift monitoring, failure modes, and human escalation are documented.
- [ ] Claims and disclosures have legal/compliance approval for the launch jurisdiction.

## Operations

- [ ] Monitoring and paging are tested; dashboards cover availability, latency, errors, freshness, jobs, quality events, resources, and backup age.
- [ ] Encrypted backups meet approved RPO; an isolated restore drill meets approved RTO.
- [ ] Rollback, provider outage, database outage, credential compromise, data correction, and AI-provider failure exercises are complete.
- [ ] Support ownership, maintenance windows, status communication, and post-launch review are scheduled.

Approval record: release ___; commit ___; environment ___; date ___; engineering ___; security ___; operations ___; legal/compliance ___.
