-- Additive M1 migration. Existing portfolio and analytical tables are preserved.

ALTER TABLE instruments
  ADD COLUMN isin VARCHAR(12),
  ADD COLUMN listing_status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
  ADD COLUMN listed_on DATE,
  ADD COLUMN delisted_on DATE,
  ADD COLUMN source_id BIGINT REFERENCES data_sources(id),
  ADD COLUMN source_revision VARCHAR(120),
  ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

ALTER TABLE instruments
  ADD CONSTRAINT chk_instrument_isin CHECK (isin IS NULL OR isin ~ '^[A-Z]{2}[A-Z0-9]{9}[0-9]$'),
  ADD CONSTRAINT chk_instrument_listing_status CHECK (listing_status IN ('ACTIVE','INACTIVE','DELISTED')),
  ADD CONSTRAINT chk_instrument_listing_dates CHECK (delisted_on IS NULL OR listed_on IS NULL OR delisted_on >= listed_on);

CREATE UNIQUE INDEX uq_instruments_exchange_symbol_series_normalized ON instruments(exchange_id,symbol,COALESCE(series,''));
CREATE UNIQUE INDEX uq_instruments_exchange_isin ON instruments(exchange_id,isin) WHERE isin IS NOT NULL;
CREATE INDEX idx_instruments_listing_status ON instruments(exchange_id,listing_status);

ALTER TABLE data_sources
  ADD COLUMN provider_url TEXT,
  ADD COLUMN license_scope VARCHAR(80) NOT NULL DEFAULT 'UNVERIFIED',
  ADD COLUMN verified_at TIMESTAMPTZ,
  ADD COLUMN notes TEXT;

INSERT INTO data_sources(source_code,display_name,source_class,access_mode,license_reference,enabled,provider_url,license_scope,verified_at,notes)
VALUES ('MANUAL_CSV','User-supplied CSV files','MANUAL_FILE','LOCAL_UPLOAD',
        'User must have lawful rights to import and retain every uploaded file.',TRUE,NULL,
        'USER_ATTESTED_LOCAL_RESEARCH',now(),
        'No automated exchange scraping. Source revision and adjustment status are mandatory.')
ON CONFLICT(source_code) DO UPDATE SET display_name=EXCLUDED.display_name,enabled=TRUE,
  license_reference=EXCLUDED.license_reference,license_scope=EXCLUDED.license_scope,notes=EXCLUDED.notes;

ALTER TABLE ingestion_runs
  ADD COLUMN artifact_name VARCHAR(255),
  ADD COLUMN artifact_sha256 CHAR(64),
  ADD COLUMN source_revision VARCHAR(120),
  ADD COLUMN quality_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN failure_count BIGINT NOT NULL DEFAULT 0;

ALTER TABLE ingestion_runs
  ADD CONSTRAINT chk_ingestion_status CHECK (status IN ('RUNNING','SUCCESS','FAILED','DUPLICATE')),
  ADD CONSTRAINT chk_ingestion_sha CHECK (artifact_sha256 IS NULL OR artifact_sha256 ~ '^[0-9a-f]{64}$');

CREATE UNIQUE INDEX uq_successful_ingestion_artifact ON ingestion_runs(source_id,job_name,artifact_sha256) WHERE status='SUCCESS';

ALTER TABLE data_quality_events
  ADD COLUMN ingestion_run_id UUID REFERENCES ingestion_runs(id),
  ADD COLUMN event_time TIMESTAMPTZ;
CREATE INDEX idx_quality_unresolved ON data_quality_events(severity,event_type,observed_at DESC) WHERE resolved_at IS NULL;
CREATE INDEX idx_quality_run ON data_quality_events(ingestion_run_id);

ALTER TABLE market_sessions
  ADD COLUMN ingestion_run_id UUID REFERENCES ingestion_runs(id),
  ADD COLUMN source_revision VARCHAR(120),
  ADD COLUMN received_at TIMESTAMPTZ NOT NULL DEFAULT now();

ALTER TABLE corporate_actions
  ADD COLUMN ingestion_run_id UUID REFERENCES ingestion_runs(id),
  ADD COLUMN received_at TIMESTAMPTZ NOT NULL DEFAULT now();
CREATE UNIQUE INDEX uq_corporate_action_revision ON corporate_actions(instrument_id,action_type,ex_date,COALESCE(source_revision,''));
CREATE INDEX idx_corporate_actions_instrument_date ON corporate_actions(instrument_id,ex_date DESC);

ALTER TABLE market_candles
  ADD COLUMN ingestion_run_id UUID REFERENCES ingestion_runs(id),
  ADD COLUMN received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  ADD COLUMN source_revision VARCHAR(120),
  ADD COLUMN adjustment_status VARCHAR(24) NOT NULL DEFAULT 'RAW_UNADJUSTED';

ALTER TABLE market_candles
  ADD CONSTRAINT chk_candle_prices_positive CHECK (open > 0 AND high > 0 AND low > 0 AND close > 0),
  ADD CONSTRAINT chk_candle_ohlc CHECK (high >= GREATEST(open,close,low) AND low <= LEAST(open,close,high)),
  ADD CONSTRAINT chk_candle_volume CHECK (volume >= 0),
  ADD CONSTRAINT chk_candle_adjustment CHECK (adjustment_status IN ('RAW_UNADJUSTED','ADJUSTED'));

CREATE INDEX idx_candles_source_received ON market_candles(source_id,received_at DESC);
CREATE INDEX idx_candles_run ON market_candles(ingestion_run_id);
