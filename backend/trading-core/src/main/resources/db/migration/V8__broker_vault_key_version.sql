-- Versioned envelope key selection for safe staged vault rotation.
ALTER TABLE broker_credentials
  ADD COLUMN IF NOT EXISTS key_version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE broker_credentials
  ADD CONSTRAINT broker_credentials_key_version_positive CHECK (key_version > 0);
CREATE INDEX IF NOT EXISTS idx_broker_credentials_key_version ON broker_credentials(key_version);
