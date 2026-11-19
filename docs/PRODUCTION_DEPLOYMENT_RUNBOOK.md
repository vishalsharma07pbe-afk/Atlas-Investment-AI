# Production deployment runbook

## Scope and prerequisites

This runbook describes the repository's production contract. It does not authorize internet exposure. Before deployment, provision an approved host, private network, TLS termination, secret manager, encrypted storage, monitoring receiver, and licensed provider access.

Use an immutable release tag such as `v3.0.0`; never deploy `latest`. Required configuration is stored outside Git:

- `ATLAS_IMAGE_NAMESPACE`, `ATLAS_RELEASE_TAG`, `ATLAS_HTTP_PORT`
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `ATLAS_JWT_SECRET`, `ATLAS_VAULT_MASTER_KEY`, `INTERNAL_SERVICE_TOKEN`
- only explicitly approved provider and AI settings

Generate every secret independently. Do not copy local development secrets into production.

## Release and deploy

1. Merge a reviewed commit with green CI.
2. Create a signed SemVer tag. The release workflow re-runs CI and publishes three immutable GHCR images with SBOM and provenance.
3. On the approved host, authenticate to GHCR and create a root-readable environment file outside the checkout.
4. Validate without starting services:
   `docker compose --env-file /secure/path/atlas.env -f docker-compose.production.yml config --quiet`
5. Back up the current release using `ATLAS_PRODUCTION_ENV_FILE=/secure/path/atlas.env ATLAS_BACKUP_DIR=/secure/staging scripts/backup-production.sh` and verify it using `scripts/verify-production-backup.py`.
6. Pull images, then start with `docker compose --env-file /secure/path/atlas.env -f docker-compose.production.yml up -d`.
7. Confirm every health check, migration, login, portfolio read, data-health page, AI-disabled fallback, and logout.
8. Run `python3 scripts/p3_smoke.py --base-url http://127.0.0.1:8088` on the host.
9. Record image digests, migration version, test output, operator, time, and approval in the release record.

## Network boundary

Only the frontend gateway is published, on loopback by default. PostgreSQL, Spring, and FastAPI have no host ports in the production contract. TLS and external authentication controls belong to the approved edge. Do not change the binding to `0.0.0.0` merely to make remote access convenient.

## Rollback

Application rollback means setting `ATLAS_RELEASE_TAG` to the previously approved immutable tag and recreating application containers. Database rollback is not automatic: Flyway migrations are forward-only. If a release changes data incompatibly, stop and execute the tested disaster-recovery plan instead of deleting volumes or editing Flyway history.

## Monitoring

Probe `/healthz`, `/api/v1/health`, `/api/v1/data-health/summary`, and the intelligence `/health` route through an authenticated internal monitor. Alert on consecutive failures, excessive latency, stale provider observations, unresolved critical quality events, backup age, certificate expiry, disk usage, container restarts, and authentication-rate-limit spikes. Never put tokens or response bodies containing portfolio data into alert messages.

