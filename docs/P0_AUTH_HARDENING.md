# P0-4 hardening — operator runbook

PR #101 adds tested AES-GCM decryption, tamper rejection and re-encryption under a new key, persistent JWT denylist and login failure tables, and service-to-service AI authentication.

**Legacy rows:** Never claim orphaned holdings automatically. After backing up PostgreSQL, select the exact target UUID from `atlas_users`, inspect orphaned holdings and conflicts, then explicitly update `personal_holdings.user_id` in a transaction. Verify zero NULL owners before executing `ALTER TABLE personal_holdings ALTER COLUMN user_id SET NOT NULL`. The migration deliberately does not enforce NOT NULL until this manual action is complete.

**Service token:** Generate `openssl rand -base64 32`, set the same value for `INTERNAL_SERVICE_TOKEN` in backend and intelligence containers. AI proxy stays off until this is configured and tested. Keep the intelligence service bound to loopback on the host.

**Security limitations:** Never paste Upstox secrets into chat or GitHub. Vault rotation requires a transactional database re-encryption operation, not merely changing the environment key. A refresh-token workflow and strict data isolation of other internal Python endpoints remain outside this PR.
