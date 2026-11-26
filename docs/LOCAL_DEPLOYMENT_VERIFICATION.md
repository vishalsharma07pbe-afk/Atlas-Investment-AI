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

## Production gateway security boundary
The production image preserves the configured browser security headers on HTML, cached assets and streaming routes even where Nginx location-level headers override inheritance. Browser-facing proxy paths strip X-Atlas-Service-Token; direct internal container-to-container calls are unaffected. CI exercises authenticated and anonymous notification reads, session revocation and rejection of the disposable service token through the browser gateway. These checks do not certify a multi-user deployment: development ports/proxy are intended only for trusted local use. The Python research-notes journal now verifies the Spring session on each CRUD request and stores notes by account UUID. Do not expose either environment publicly or share accounts until remaining isolation and deployment acceptance is complete.

### Existing research notes after upgrade
The legacy installation-wide `data/research-journal/entries.json` (production: `/app/journal/entries.json` in its mounted journal volume) is preserved, but never exposed or assigned automatically. New notes use `owners/<authenticated-account-UUID>.json` in the same journal directory, included in the existing backup root. If legacy notes exist, back up and stop intelligence, verify the intended account UUID using that account's authenticated `/api/v1/auth/me` locally, then copy the validated legacy JSON to that account's owner file **only if the destination does not exist**. Do not assign ambiguous shared notes or overwrite new notes; keep the original as a protected offline backup. Create the owners directory with restricted access and ensure the intelligence container user can read/write it. Restart intelligence and verify the intended account's notes. If an owner file already exists, keep both files and reconcile offline; no automatic merge or deletion is performed. Never expose these paths or credentials publicly.
