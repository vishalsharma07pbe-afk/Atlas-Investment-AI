-- Existing records remain valid recorded observations, not certified closing valuations.
ALTER TABLE portfolio_valuation_snapshots
  ADD COLUMN capture_source VARCHAR(24) NOT NULL DEFAULT 'LEGACY_RECORDED',
  ADD COLUMN oldest_price_at TIMESTAMPTZ,
  ADD COLUMN newest_price_at TIMESTAMPTZ,
  ADD CONSTRAINT portfolio_valuation_capture_source_check
    CHECK (capture_source IN ('LEGACY_RECORDED','MANUAL_RECORDED','AUTO_RECORDED')),
  ADD CONSTRAINT portfolio_valuation_observation_order_check
    CHECK (oldest_price_at IS NULL OR newest_price_at IS NULL OR oldest_price_at<=newest_price_at);
