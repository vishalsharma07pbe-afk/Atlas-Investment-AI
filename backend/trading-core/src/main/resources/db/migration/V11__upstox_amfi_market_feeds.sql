INSERT INTO data_sources(source_code,display_name,source_class,access_mode,enabled,provider_url,license_scope)
VALUES ('UPSTOX','Upstox authorized market data','BROKER_API','USER_OAUTH',true,'https://api.upstox.com','USER_AUTHORIZED'),
('AMFI','Association of Mutual Funds in India','PUBLIC_FEED','PUBLIC',true,'https://portal.amfiindia.com/spages/NAVAll.txt','PUBLIC'),
('MFAPI','mfapi.in historical NAV','PUBLIC_API','PUBLIC',true,'https://api.mfapi.in','PUBLIC')
ON CONFLICT(source_code) DO UPDATE SET enabled=true;
CREATE TABLE upstox_instrument_map(instrument_key TEXT PRIMARY KEY,exchange_code VARCHAR(10) NOT NULL,isin VARCHAR(12),trading_symbol TEXT NOT NULL,instrument_type TEXT,updated_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE INDEX idx_upstox_search_symbol ON upstox_instrument_map(lower(trading_symbol) text_pattern_ops);
CREATE INDEX idx_upstox_isin ON upstox_instrument_map(isin);
CREATE TABLE market_quotes(instrument_key TEXT PRIMARY KEY REFERENCES upstox_instrument_map(instrument_key),ltp NUMERIC(20,6) NOT NULL CHECK(ltp>=0),source_code VARCHAR(20) NOT NULL,quoted_at TIMESTAMPTZ NOT NULL,received_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE mutual_fund_schemes(scheme_code BIGINT PRIMARY KEY,scheme_name TEXT NOT NULL,isin_growth TEXT,isin_reinvestment TEXT,amc_name TEXT,category TEXT,last_synced_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE INDEX idx_mf_scheme_search ON mutual_fund_schemes(lower(scheme_name) text_pattern_ops);
CREATE TABLE mutual_fund_nav(scheme_code BIGINT NOT NULL REFERENCES mutual_fund_schemes(scheme_code),nav_date DATE NOT NULL,nav NUMERIC(20,6) NOT NULL CHECK(nav>0),source_code VARCHAR(20) NOT NULL,received_at TIMESTAMPTZ NOT NULL DEFAULT now(),PRIMARY KEY(scheme_code,nav_date));
CREATE TABLE market_provider_runs(id BIGSERIAL PRIMARY KEY,provider VARCHAR(20) NOT NULL,job_name VARCHAR(80) NOT NULL,started_at TIMESTAMPTZ NOT NULL DEFAULT now(),finished_at TIMESTAMPTZ,status VARCHAR(20) NOT NULL,attempts INT NOT NULL DEFAULT 0,next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),error_message TEXT);
CREATE INDEX idx_provider_runs_due ON market_provider_runs(next_attempt_at) WHERE status='RETRY';
