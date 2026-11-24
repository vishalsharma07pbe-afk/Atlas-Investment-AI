# ATLAS P3 implementation status

Updated: 2026-11-24

P3 adds a production **deployment contract**, release automation, operational safety tools, accessibility improvements, onboarding, and launch documentation. It does not claim that a public production environment exists.

## Implemented

- Multi-stage production frontend image serving static assets through Nginx rather than Vite's development server.
- Same-origin reverse proxy for Spring and FastAPI, security headers, bounded request sizes, health checks, non-root host exposure, restart policies, private service networks, read-only application filesystems, and resource ceilings.
- The production intelligence proxy is protected by an application-session subrequest; direct anonymous access through the production gateway is denied.
- Production sessions can be forced onto Secure cookies, while unsafe cookie-authenticated mutations are protected by same-origin checks.
- Pull-request dependency review and CodeQL scanning cover the supported Java, JavaScript/TypeScript, and Python sources.
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

Latest repository validation evidence:

- frontend rerun on 2026-11-24: 48 test files and 86 tests passed; production TypeScript/Vite build passed;
- operations rerun on 2026-11-24: 7 safeguards passed and production Compose rendered with non-secret placeholders;
- backend validation on 2026-11-19: the Spring/Testcontainers suite passed and the production image compiled and packaged successfully;
- intelligence validation on 2026-11-19: 383 tests passed inside the Python 3.12 production image;
- image validation on 2026-11-19: all three production images built successfully as non-root runtimes;
- production Compose rendered successfully with non-secret placeholders; and
- the built Nginx configuration passed `nginx -t`.
- an isolated read-only frontend runtime passed 100/100 bounded health requests
  with 0% errors and 20.8 ms p95 on the local validation host.

An image rebuild was attempted on 2026-11-24, but Docker Desktop was not running.
The source build and static production configuration checks still passed; image
revalidation must be repeated after the local Docker daemon is started.

These checks are release evidence, not proof of a deployed environment, licensed
provider access, disaster-recovery success, or production capacity.

