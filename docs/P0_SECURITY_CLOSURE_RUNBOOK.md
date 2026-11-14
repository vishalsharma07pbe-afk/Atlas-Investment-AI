# P0-4 operator procedures (in progress)

Actual schema names are `personal_holdings.user_id`, not `portfolio_holdings.owner_user_id`.

**Legacy owner claim:** Before deploying Flyway V7 against an existing database with orphaned holdings, back up PostgreSQL and run:
```sh
psql -v ON_ERROR_STOP=1 -v owner_email='YOUR_EXISTING_ACCOUNT_EMAIL' -f infrastructure/postgres/claim_legacy_holdings.psql
```
Review orphaned rows and target identity before running. V7 fails startup when unclaimed rows remain, then enforces NOT NULL.

**Vault:** `VaultRotationService.rotate(oldKey,newKey)` uses a database transaction and locks credential rows. It is a service primitive, not an exposed admin endpoint or complete operational key-switch procedure. A coordinated active-key switch, crash recovery and end-to-end tests are still required. Never rotate by changing `.env` alone.

**AI:** Proxy remains off by default until real Spring-to-Python security tests are green. Both services require a shared random `INTERNAL_SERVICE_TOKEN` to enable the bridge.
