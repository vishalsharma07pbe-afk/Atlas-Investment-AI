CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE exchanges (
 id SMALLSERIAL PRIMARY KEY, code VARCHAR(10) UNIQUE NOT NULL,
 name VARCHAR(100) NOT NULL, timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Kolkata'
);
INSERT INTO exchanges(code,name) VALUES
 ('NSE','National Stock Exchange of India'),('BSE','BSE Limited')
ON CONFLICT DO NOTHING;

CREATE TABLE issuers (
 id BIGSERIAL PRIMARY KEY, isin VARCHAR(12) UNIQUE, legal_name VARCHAR(250) NOT NULL,
 sector VARCHAR(120), industry VARCHAR(160), created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE instruments (
 id BIGSERIAL PRIMARY KEY, issuer_id BIGINT REFERENCES issuers(id),
 exchange_id SMALLINT NOT NULL REFERENCES exchanges(id), symbol VARCHAR(50) NOT NULL,
 exchange_token VARCHAR(80), series VARCHAR(10), instrument_type VARCHAR(20) NOT NULL DEFAULT 'EQUITY',
 tick_size NUMERIC(12,6), lot_size INTEGER, active BOOLEAN NOT NULL DEFAULT TRUE,
 source VARCHAR(60) NOT NULL, valid_from TIMESTAMPTZ, valid_to TIMESTAMPTZ,
 UNIQUE(exchange_id,symbol,series)
);
CREATE INDEX idx_instruments_issuer ON instruments(issuer_id);
CREATE INDEX idx_instruments_active ON instruments(active,exchange_id);

CREATE TABLE data_sources (
 id BIGSERIAL PRIMARY KEY, source_code VARCHAR(60) UNIQUE NOT NULL,
 display_name VARCHAR(160) NOT NULL, source_class VARCHAR(40) NOT NULL,
 access_mode VARCHAR(30) NOT NULL, license_reference TEXT,
 enabled BOOLEAN NOT NULL DEFAULT FALSE, expected_cadence_seconds INTEGER,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE ingestion_runs (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), source_id BIGINT REFERENCES data_sources(id),
 job_name VARCHAR(120) NOT NULL, started_at TIMESTAMPTZ NOT NULL,
 finished_at TIMESTAMPTZ, status VARCHAR(24) NOT NULL,
 records_seen BIGINT DEFAULT 0, records_written BIGINT DEFAULT 0,
 error_message TEXT, cursor_value TEXT
);
CREATE INDEX idx_ingestion_runs_source_time ON ingestion_runs(source_id,started_at DESC);
CREATE TABLE data_quality_events (
 id BIGSERIAL PRIMARY KEY, source_id BIGINT REFERENCES data_sources(id),
 instrument_id BIGINT REFERENCES instruments(id), severity VARCHAR(16) NOT NULL,
 event_type VARCHAR(60) NOT NULL, observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 details JSONB NOT NULL DEFAULT '{}'::jsonb, resolved_at TIMESTAMPTZ
);

CREATE TABLE market_quotes (
 instrument_id BIGINT NOT NULL REFERENCES instruments(id), observed_at TIMESTAMPTZ NOT NULL,
 source_id BIGINT REFERENCES data_sources(id), exchange_time TIMESTAMPTZ,
 ltp NUMERIC(18,6), bid NUMERIC(18,6), ask NUMERIC(18,6),
 bid_qty BIGINT, ask_qty BIGINT, day_volume BIGINT, feed_sequence BIGINT,
 quality_status VARCHAR(24) NOT NULL DEFAULT 'UNVERIFIED',
 PRIMARY KEY(instrument_id,observed_at)
);
SELECT create_hypertable('market_quotes','observed_at',if_not_exists=>TRUE);

CREATE TABLE market_candles (
 instrument_id BIGINT NOT NULL REFERENCES instruments(id), timeframe VARCHAR(8) NOT NULL,
 candle_time TIMESTAMPTZ NOT NULL, source_id BIGINT REFERENCES data_sources(id),
 open NUMERIC(18,6) NOT NULL, high NUMERIC(18,6) NOT NULL,
 low NUMERIC(18,6) NOT NULL, close NUMERIC(18,6) NOT NULL,
 volume BIGINT NOT NULL, is_complete BOOLEAN NOT NULL DEFAULT FALSE,
 quality_status VARCHAR(24) NOT NULL DEFAULT 'UNVERIFIED', revision INTEGER NOT NULL DEFAULT 1,
 PRIMARY KEY(instrument_id,timeframe,candle_time)
);
SELECT create_hypertable('market_candles','candle_time',if_not_exists=>TRUE);
CREATE INDEX idx_candles_lookup ON market_candles(instrument_id,timeframe,candle_time DESC);

CREATE TABLE market_sessions (
 exchange_id SMALLINT NOT NULL REFERENCES exchanges(id), session_date DATE NOT NULL,
 session_type VARCHAR(30) NOT NULL, open_time TIMESTAMPTZ, close_time TIMESTAMPTZ,
 is_trading_day BOOLEAN NOT NULL, source_id BIGINT REFERENCES data_sources(id),
 PRIMARY KEY(exchange_id,session_date,session_type)
);
CREATE TABLE corporate_actions (
 id BIGSERIAL PRIMARY KEY, issuer_id BIGINT REFERENCES issuers(id),
 instrument_id BIGINT REFERENCES instruments(id), action_type VARCHAR(40) NOT NULL,
 ex_date DATE, ratio NUMERIC(18,6), cash_amount NUMERIC(18,6),
 source_id BIGINT REFERENCES data_sources(id), source_revision VARCHAR(80),
 raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE institutional_flows (
 id BIGSERIAL PRIMARY KEY, trade_date DATE NOT NULL, market VARCHAR(20) NOT NULL DEFAULT 'EQUITY',
 participant VARCHAR(20) NOT NULL, buy_value_crore NUMERIC(20,4),
 sell_value_crore NUMERIC(20,4), net_value_crore NUMERIC(20,4),
 publication_status VARCHAR(20) NOT NULL, source_id BIGINT REFERENCES data_sources(id),
 published_at TIMESTAMPTZ, ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 source_revision VARCHAR(80)
);
CREATE INDEX idx_inst_flows_date ON institutional_flows(trade_date DESC,participant);
CREATE TABLE participant_position_reports (
 id BIGSERIAL PRIMARY KEY, report_date DATE NOT NULL, participant_category VARCHAR(40) NOT NULL,
 instrument_scope VARCHAR(40) NOT NULL, metric_code VARCHAR(60) NOT NULL,
 metric_value NUMERIC(24,6), unit VARCHAR(30), source_id BIGINT REFERENCES data_sources(id),
 published_at TIMESTAMPTZ, quality_status VARCHAR(24) NOT NULL
);
CREATE TABLE disclosed_deals (
 id BIGSERIAL PRIMARY KEY, exchange_id SMALLINT REFERENCES exchanges(id),
 instrument_id BIGINT REFERENCES instruments(id), deal_date DATE NOT NULL,
 deal_type VARCHAR(20) NOT NULL, client_name VARCHAR(250), side VARCHAR(8) NOT NULL,
 quantity BIGINT NOT NULL, price NUMERIC(18,6), source_id BIGINT REFERENCES data_sources(id),
 published_at TIMESTAMPTZ, source_revision VARCHAR(80), raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX idx_deals_instrument_date ON disclosed_deals(instrument_id,deal_date DESC);
CREATE TABLE short_sell_disclosures (
 id BIGSERIAL PRIMARY KEY, instrument_id BIGINT REFERENCES instruments(id),
 report_date DATE NOT NULL, disclosed_quantity BIGINT,
 source_id BIGINT REFERENCES data_sources(id), published_at TIMESTAMPTZ,
 raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE news_articles (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), source_code VARCHAR(80) NOT NULL,
 external_id VARCHAR(250), canonical_url TEXT, headline TEXT NOT NULL, body_text TEXT,
 language_code VARCHAR(12), publisher VARCHAR(200), published_at TIMESTAMPTZ,
 first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ,
 content_hash CHAR(64) NOT NULL, source_trust_score NUMERIC(5,2),
 UNIQUE(source_code,external_id)
);
CREATE INDEX idx_news_published ON news_articles(published_at DESC);
CREATE INDEX idx_news_hash ON news_articles(content_hash);
CREATE TABLE news_entities (
 article_id UUID NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
 issuer_id BIGINT REFERENCES issuers(id), entity_name VARCHAR(250) NOT NULL,
 entity_type VARCHAR(40), relevance_score NUMERIC(5,4),
 PRIMARY KEY(article_id,entity_name)
);
CREATE TABLE news_events (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), article_id UUID NOT NULL REFERENCES news_articles(id),
 event_type VARCHAR(60) NOT NULL, geography VARCHAR(80), severity_score NUMERIC(5,4),
 sentiment_score NUMERIC(6,5), confidence NUMERIC(6,5),
 event_start TIMESTAMPTZ, event_end TIMESTAMPTZ, extracted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE instrument_features (
 instrument_id BIGINT NOT NULL REFERENCES instruments(id), feature_time TIMESTAMPTZ NOT NULL,
 timeframe VARCHAR(8) NOT NULL, feature_version VARCHAR(40) NOT NULL,
 feature_set JSONB NOT NULL, source_watermark TIMESTAMPTZ,
 quality_status VARCHAR(24) NOT NULL,
 PRIMARY KEY(instrument_id,feature_time,timeframe,feature_version)
);
SELECT create_hypertable('instrument_features','feature_time',if_not_exists=>TRUE);
CREATE TABLE trap_events (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), instrument_id BIGINT NOT NULL REFERENCES instruments(id),
 detected_at TIMESTAMPTZ NOT NULL, timeframe VARCHAR(8) NOT NULL,
 trap_type VARCHAR(30) NOT NULL, score NUMERIC(5,2) NOT NULL,
 evidence JSONB NOT NULL, invalidation_level NUMERIC(18,6), status VARCHAR(24) NOT NULL
);
CREATE TABLE liquidity_events (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), instrument_id BIGINT NOT NULL REFERENCES instruments(id),
 observed_at TIMESTAMPTZ NOT NULL, event_type VARCHAR(40) NOT NULL,
 score NUMERIC(5,2), evidence JSONB NOT NULL, data_granularity VARCHAR(30) NOT NULL
);

CREATE TABLE model_registry (
 id BIGSERIAL PRIMARY KEY, model_name VARCHAR(120) NOT NULL, model_version VARCHAR(60) NOT NULL,
 artifact_uri TEXT, training_start DATE, training_end DATE, validation_start DATE,
 validation_end DATE, feature_version VARCHAR(40), metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
 status VARCHAR(24) NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(model_name,model_version)
);
CREATE TABLE predictions (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), instrument_id BIGINT NOT NULL REFERENCES instruments(id),
 model_id BIGINT REFERENCES model_registry(id), horizon VARCHAR(20) NOT NULL,
 as_of TIMESTAMPTZ NOT NULL, probability_up NUMERIC(6,5), probability_down NUMERIC(6,5),
 probability_neutral NUMERIC(6,5), expected_return NUMERIC(12,6),
 calibration_version VARCHAR(60), feature_watermark TIMESTAMPTZ, expires_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE trading_signals (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), instrument_id BIGINT NOT NULL REFERENCES instruments(id),
 prediction_id UUID REFERENCES predictions(id), strategy VARCHAR(80) NOT NULL,
 horizon VARCHAR(20) NOT NULL, direction VARCHAR(8) NOT NULL,
 entry_min NUMERIC(18,6), entry_max NUMERIC(18,6), trigger_rule JSONB NOT NULL,
 stop_loss NUMERIC(18,6), target_1 NUMERIC(18,6), target_2 NUMERIC(18,6),
 expected_net_rr NUMERIC(8,4), quality_score NUMERIC(5,2),
 calibrated_probability NUMERIC(6,5), gate_results JSONB NOT NULL,
 evidence_refs JSONB NOT NULL, status VARCHAR(30) NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), expires_at TIMESTAMPTZ NOT NULL,
 invalidated_at TIMESTAMPTZ
);
CREATE INDEX idx_signals_status_created ON trading_signals(status,created_at DESC);
CREATE TABLE signal_outcomes (
 id BIGSERIAL PRIMARY KEY, signal_id UUID NOT NULL REFERENCES trading_signals(id),
 evaluated_at TIMESTAMPTZ NOT NULL, entry_fill NUMERIC(18,6), exit_price NUMERIC(18,6),
 gross_pnl NUMERIC(18,6), estimated_costs NUMERIC(18,6), net_pnl NUMERIC(18,6),
 outcome VARCHAR(24), evaluation_policy VARCHAR(40) NOT NULL
);
CREATE TABLE alert_preferences (
 id BIGSERIAL PRIMARY KEY, user_id UUID NOT NULL, channel VARCHAR(20) NOT NULL,
 min_quality_score NUMERIC(5,2) NOT NULL DEFAULT 90, enabled BOOLEAN NOT NULL DEFAULT TRUE,
 config JSONB NOT NULL DEFAULT '{}'::jsonb, UNIQUE(user_id,channel)
);
CREATE TABLE alert_deliveries (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID NOT NULL,
 signal_id UUID REFERENCES trading_signals(id), channel VARCHAR(20) NOT NULL,
 status VARCHAR(20) NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 delivered_at TIMESTAMPTZ, error_message TEXT
);
