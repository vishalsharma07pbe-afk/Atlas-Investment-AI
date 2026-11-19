# ATLAS P3 implementation status

Updated: 2026-11-19

P3 adds a production **deployment contract**, release automation, operational safety tools, accessibility improvements, onboarding, and launch documentation. It does not claim that a public production environment exists.

## Implemented

- Multi-stage production frontend image serving static assets through Nginx rather than Vite's development server.
- Same-origin reverse proxy for Spring and FastAPI, security headers, bounded request sizes, health checks, non-root host exposure, restart policies, private service networks, read-only application filesystems, and resource ceilings.
- Tag-triggered GitHub release workflow that first runs the full CI workflow, then publishes immutable backend, intelligence, and frontend images to GHCR with SBOM and provenance attestations.
- Quiesced PostgreSQL and intelligence-state backup script, checksum manifest, path-safe offline verifier, and restore-drill procedure.
- Bounded HTTP smoke/load tool with latency and error-rate gates. Remote targets require an explicit flag.
- Skip navigation, semantic navigation labels, keyboard Escape handling for Appearance, accessible live loading/error/feed states, responsive first-run onboarding, and an always-available Help action.
- Authenticated server-sent-event delivery for validated Upstox WebSocket ticks. The index strip and selected-stock view update on provider events, reconnect automatically, and no longer depend on 30-second/five-second browser polling.
- Production, disaster-recovery, user, legal, and launch-acceptance documentation.

## Deliberately blocked or operator-owned

- No production host, DNS record, TLS certificate, cloud database, secret manager, alert receiver, or licensed market-data contract was created from this repository.
- The production gateway binds to loopback by default. An operator must put an approved TLS reverse proxy or private access layer in front of it.
- Release automation publishes images; it does not deploy them automatically to an unknown environment.
- Backups are not durable until encrypted, copied to a separate failure domain, retained under policy, and proven through an isolated restore drill.
- Load smoke results from a laptop are not a production capacity benchmark.

## Acceptance evidence

See `docs/LAUNCH_ACCEPTANCE.md`. A launch stays blocked until every required gate has an owner, dated evidence, and approval.

Repository validation completed on 2026-11-19:

- frontend: 47 test files and 85 tests passed; production TypeScript/Vite build passed;
- intelligence: 381 tests passed inside the Python 3.12 production image;
- operations safeguards: 6 tests passed;
- backend production image compiled and packaged successfully;
- all three production images built successfully as non-root runtimes;
- production Compose rendered successfully with non-secret placeholders; and
- the built Nginx configuration passed `nginx -t`.
- an isolated read-only frontend runtime passed 100/100 bounded health requests
  with 0% errors and 20.8 ms p95 on the local validation host.

These checks are release evidence, not proof of a deployed environment, licensed
provider access, disaster-recovery success, or production capacity.

