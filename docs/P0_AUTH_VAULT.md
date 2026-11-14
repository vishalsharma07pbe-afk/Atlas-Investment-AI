# P0-4 authentication and token vault — partial implementation

## Setup
Generate independent base64 secrets locally (never commit them):
```bash
openssl rand -base64 32
```
Set `ATLAS_JWT_SECRET` and `ATLAS_VAULT_MASTER_KEY` to two different values in your private Docker `.env`. Set `ALLOW_REGISTRATION=true` for initial account creation, then set it to false and restart the backend. The JWT expires in 15 minutes; there is no refresh flow yet.

Endpoints: `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `GET /api/v1/auth/me`, `POST /api/v1/broker/upstox/token`. Supply `Authorization: Bearer <access_token>` for authenticated requests. Upstox tokens are AES-256-GCM encrypted using a random nonce and per-user associated data, never returned by the API.

Existing holdings from previous local-alpha versions are deliberately **not silently assigned to an invented default user**. Migration leaves legacy rows with NULL user_id and they are invisible to authenticated users. A one-time, explicitly authorized owner backfill is required before adding NOT NULL. Back up the database first.

**Security gaps before production:** refresh token/session revocation, login throttling, credential rotation/recovery, explicit legacy-data ownership migration, row-level database policies, AI report persistence/isolation, authenticated internal intelligence service-to-service calls, and securely injecting derived portfolio weights. Spring Boot AI proxy remains disabled by default; do not enable while internal intelligence endpoints can be accessed directly or before cross-service authorization is enforced. Other existing dashboard calls must add bearer authorization.

The security migration exists in both fresh-volume Docker init and Flyway V5 for existing databases. Never assume init scripts rerun on existing PostgreSQL volumes.
