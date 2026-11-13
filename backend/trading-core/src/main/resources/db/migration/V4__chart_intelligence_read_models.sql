-- Additive Milestone 2 identity/read-model support. No holdings or candles are rewritten.
ALTER TABLE instruments ADD COLUMN security_name VARCHAR(250);

CREATE TABLE instrument_symbol_history (
  id BIGSERIAL PRIMARY KEY,
  instrument_id BIGINT NOT NULL REFERENCES instruments(id),
  exchange_id SMALLINT NOT NULL REFERENCES exchanges(id),
  symbol VARCHAR(50) NOT NULL,
  series VARCHAR(10),
  valid_from DATE NOT NULL,
  valid_to DATE,
  source_id BIGINT REFERENCES data_sources(id),
  source_revision VARCHAR(120),
  ingestion_run_id UUID REFERENCES ingestion_runs(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT chk_symbol_history_dates CHECK (valid_to IS NULL OR valid_to >= valid_from)
);
CREATE UNIQUE INDEX uq_symbol_history_identity ON instrument_symbol_history(instrument_id,exchange_id,symbol,COALESCE(series,''),valid_from);
CREATE INDEX idx_symbol_history_lookup ON instrument_symbol_history(exchange_id,symbol,valid_from DESC);
CREATE INDEX idx_instruments_security_name_trgm_fallback ON instruments(lower(security_name)) WHERE security_name IS NOT NULL;

ALTER TABLE instrument_features
  ADD COLUMN source_candle_revision INTEGER,
  ADD COLUMN adjustment_status VARCHAR(24),
  ADD COLUMN calculation_version VARCHAR(40),
  ADD COLUMN ingestion_run_id UUID REFERENCES ingestion_runs(id);

ALTER TABLE instrument_features ADD CONSTRAINT chk_feature_adjustment
  CHECK (adjustment_status IS NULL OR adjustment_status IN ('RAW_UNADJUSTED','ADJUSTED'));
