-- Additive portfolio tracking. Active positions stay in personal_holdings;
-- completed investments live in a separate user-owned history table.
ALTER TABLE personal_holdings
  ADD COLUMN IF NOT EXISTS previous_close NUMERIC(20,6)
  CHECK(previous_close IS NULL OR previous_close >= 0);

CREATE TABLE historical_investments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES atlas_users(id) ON DELETE CASCADE,
  symbol VARCHAR(50) NOT NULL,
  display_name VARCHAR(300),
  asset_type VARCHAR(16) NOT NULL CHECK(asset_type IN ('EQUITY','MUTUAL_FUND')),
  quantity NUMERIC(20,6) NOT NULL CHECK(quantity > 0),
  average_cost NUMERIC(20,6) NOT NULL CHECK(average_cost >= 0),
  exit_price NUMERIC(20,6) NOT NULL CHECK(exit_price >= 0),
  opened_on DATE,
  closed_on DATE NOT NULL,
  notes VARCHAR(500),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK(opened_on IS NULL OR opened_on <= closed_on)
);

CREATE INDEX idx_historical_investments_user_closed
  ON historical_investments(user_id,closed_on DESC,created_at DESC);
