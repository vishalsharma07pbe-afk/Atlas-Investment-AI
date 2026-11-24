-- Persist attempts across container restarts; never change holdings or ownership.
ALTER TABLE personal_holdings ADD COLUMN last_auto_refresh_attempt_at TIMESTAMPTZ;
CREATE INDEX idx_personal_holdings_auto_refresh ON personal_holdings(last_auto_refresh_attempt_at,id);
