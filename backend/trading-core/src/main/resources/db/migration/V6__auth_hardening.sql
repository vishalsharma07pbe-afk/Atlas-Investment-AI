-- Explicit owner assignment is performed by an operator after backup, not at startup.
-- Usage in psql (replace UUID with an existing atlas_users.id):
-- BEGIN;
-- SELECT count(*) FROM personal_holdings WHERE user_id IS NULL;
-- UPDATE personal_holdings SET user_id='00000000-0000-0000-0000-000000000000'
--   WHERE user_id IS NULL;
-- SELECT count(*) FROM personal_holdings WHERE user_id IS NULL;
-- ALTER TABLE personal_holdings ALTER COLUMN user_id SET NOT NULL;
-- COMMIT;
-- Do not execute the example UUID literally. Verify intended ownership before COMMIT.
CREATE TABLE IF NOT EXISTS revoked_jwt (
 token_sha256 VARCHAR(64) PRIMARY KEY,
 user_id UUID NOT NULL REFERENCES atlas_users(id) ON DELETE CASCADE,
 expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_revoked_jwt_expiry ON revoked_jwt(expires_at);
CREATE TABLE IF NOT EXISTS auth_login_failures (
 email_hash VARCHAR(64) NOT NULL,
 ip_hash VARCHAR(64) NOT NULL,
 attempted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_login_failures_window ON auth_login_failures(email_hash,ip_hash,attempted_at);
