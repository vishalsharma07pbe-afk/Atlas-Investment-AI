# ATLAS local deployment verification (Mac)

ATLAS is a private, local-first, research-only application. The stock and fund collection adapters require authorized data access and configured credentials; no provider access or recommendations are guaranteed by a successful Docker startup. All development published ports bind to loopback.

## Upgrade or start

1. Start Docker Desktop and confirm adequate memory and disk space.
2. Back up existing state before upgrading. Preserve your existing `.env` and named volumes. On a new installation only, copy `.env.example` to `.env` and configure strong unique credentials as documented there.
3. Run `python3 scripts/check_p0_local_config.py` and `docker compose config --quiet`. Do not print the resolved configuration or share the environment file.
4. Run `docker compose up --build -d` and `docker compose ps`. Verify healthy PostgreSQL and backend plus running frontend, intelligence and Redis.
5. Open `http://127.0.0.1:5173` and sign in with your existing local account. Verify Overview, My Portfolio, and Settings.
6. If services fail, inspect logs locally. Never share tokens, credentials, holdings or unredacted logs.
7. To stop, run `docker compose down` without volume deletion.

## Functional acceptance using authorized evidence

Run from the repository root:

```bash
python3 scripts/local_research_acceptance.py
```

For the production loopback gateway, use `--base-url http://127.0.0.1:8088`. Provide your local ATLAS login when prompted; this is not your Upstox password or token. The password is not echoed, no credential is saved, and the separate acceptance session is revoked on completion. The tool uses only fixed loopback URLs, disables environment proxies and redirects, and prints status labels without account information or portfolio values.

- **runtime:** all twelve automatic research sections processed, portfolio review contract, scheduler enabled, research-only mode and current workflow checks.
- **workflow_runtime:** current daily briefing coverage, exact canonical stock report linkage (up to five per daily horizon), strict fund result contract, portfolio-level risk, public notification revision metadata and registered durable alert job. An empty but valid research result can pass the contract; unavailable history or mismatched report identity blocks it.
- **investment_qualification:** NOT_CERTIFIED for this release. A successful contract check does not certify investment picks or validate execution, strategy, valuation or suitability.
- **stored_provider_evidence:** recent Upstox registry, validated daily history, official AMFI NAV, operator rights declarations, eligible equity history and historical fund evidence. Empty or stale data cannot pass.
- **live_feed:** OBSERVED only when the readiness endpoint reports a fresh authorized tick. A closed market can legitimately report NOT_OBSERVED. Add `--require-live` during a known live trading session if this is an acceptance requirement.

Exit code zero requires runtime and stored-provider checks to pass; `--require-live` additionally requires a fresh tick. A blocked result is diagnostic, not permission to enable provider rights without approval. A zero exit code does not establish data coverage for every instrument, provider SLA, legal authorization, verified model accuracy or suitability for trading. CI tests the same evaluator and current read contracts on deliberately empty provider evidence; actual provider access must be checked on the operator's device. No provider request, forced refresh, portfolio mutation or order is initiated by this command.

## Independent tests

- Python: `cd intelligence && python3 -m pip install -r requirements.txt && python3 -m unittest discover -s tests -v`.
- React: `cd frontend/trading-dashboard && npm ci && npm test && npm run build`.
- Backend: `cd backend/trading-core && mvn -B -ntp test` (database integration requires Docker; cross-service tests require the separate Python probe used in CI).
- Deployment: repository CI checks existing endpoints, real development HTTP and Chromium workflows, production images, gateway authorization, synthetic readiness load and isolated backup recovery.

These synthetic tests cannot verify real provider entitlements, real portfolio accuracy, representative load or real-data recovery. Preserve authentication and encrypted credential storage; do not publish the development ports or disable security controls. See the production deployment and disaster recovery runbooks for the separate production contract.
