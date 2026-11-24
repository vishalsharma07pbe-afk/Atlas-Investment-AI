-- Fresh Docker volumes only. Existing volumes are upgraded by Flyway V5.
CREATE TABLE IF NOT EXISTS atlas_users (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 email VARCHAR(254) NOT NULL UNIQUE,
 password_hash VARCHAR(100) NOT NULL,
 role VARCHAR(20) NOT NULL DEFAULT 'USER',
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS broker_credentials (
 id BIGSERIAL PRIMARY KEY,
 user_id UUID NOT NULL REFERENCES atlas_users(id) ON DELETE CASCADE,
 broker_name VARCHAR(30) NOT NULL CHECK (broker_name='UPSTOX'),
 encrypted_access_token BYTEA NOT NULL,
 iv_nonce BYTEA NOT NULL CHECK (octet_length(iv_nonce)=12),
 token_expires_at TIMESTAMPTZ NOT NULL,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(user_id,broker_name)
);
-- Do not assign existing holdings to a guessed user. Existing rows require explicit
-- owner assignment by an administrator before enforcing NOT NULL.
ALTER TABLE personal_holdings ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES atlas_users(id);
-- Drop the unique constraint before its backing index (SQLSTATE 2BP01).
ALTER TABLE personal_holdings DROP CONSTRAINT IF EXISTS personal_holdings_symbol_asset_type_key;
DROP INDEX IF EXISTS personal_holdings_symbol_asset_type_key;
CREATE UNIQUE INDEX IF NOT EXISTS uq_holdings_owner_symbol_type
 ON personal_holdings(user_id,symbol,asset_type);
CREATE INDEX IF NOT EXISTS idx_holdings_user ON personal_holdings(user_id);
