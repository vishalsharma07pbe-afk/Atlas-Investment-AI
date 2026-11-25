-- Explicit owner consent and restart-safe scheduling. No credentials or positions
-- are copied into this ledger. Existing owners remain opted out.
CREATE TABLE broker_holdings_sync (
  user_id UUID PRIMARY KEY REFERENCES atlas_users(id) ON DELETE CASCADE,
  enabled BOOLEAN NOT NULL DEFAULT false,
  status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
  credential_updated_at TIMESTAMPTZ,
  claim_id UUID,
  lease_until TIMESTAMPTZ,
  next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_attempt_at TIMESTAMPTZ,
  last_success_at TIMESTAMPTZ,
  failures INTEGER NOT NULL DEFAULT 0,
  error_code VARCHAR(80),
  CHECK (status IN ('PENDING','RUNNING','SUCCESS','RETRY','REAUTH_REQUIRED','ACCESS_REJECTED')),
  CHECK (failures >= 0)
);
CREATE INDEX idx_broker_holdings_sync_due ON broker_holdings_sync(next_attempt_at) WHERE enabled;
