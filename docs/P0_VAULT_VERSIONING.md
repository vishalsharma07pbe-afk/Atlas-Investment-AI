# P0-4 vault versioning: staged follow-up

## Verified code behavior
- V8 adds `broker_credentials.key_version` (existing rows default to version 1).
- Newly stored Upstox tokens are tagged with `ATLAS_VAULT_KEY_VERSION` (default 1).
- `VaultRotationService.rotateVersioned(oldKey,newKey,oldVersion,newVersion)` locks and rotates only old-version rows, then updates their key version in the same database transaction. Re-running the same version transition selects zero rows.
- V7 is safe on an empty `personal_holdings` table: its orphan guard finds no rows, and PostgreSQL permits `SET NOT NULL` on an empty table.

## Deployment caveats
- Rotation service is currently an internal Java API, **not** an operator CLI. It must not accept plaintext keys as command-line arguments or log them. A future CLI should load `OLD_VAULT_MASTER_KEY` and `NEW_VAULT_MASTER_KEY` from environment variables only.
- Changing `.env` is **not** an atomic operation with PostgreSQL commit. A safe cutover requires version-aware decrypt selection and a recovery path before enabling automatic writes with the new key. Do not assume `ATLAS_VAULT_PREVIOUS_KEY` is already supported.
- Do not enable the AI proxy by default until a real Spring→Python integration suite verifies JWT, internal token, sanitized exposure, and secret absence. This PR does not yet supply that test suite.
