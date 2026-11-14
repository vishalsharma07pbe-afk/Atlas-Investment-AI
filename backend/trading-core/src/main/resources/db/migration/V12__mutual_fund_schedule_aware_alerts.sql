CREATE TABLE mutual_fund_freshness_alerts(
 id BIGSERIAL PRIMARY KEY,
 scheme_code BIGINT NOT NULL REFERENCES mutual_fund_schemes(scheme_code),
 expected_nav_date DATE NOT NULL,
 observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 resolved_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX uq_mf_active_stale ON mutual_fund_freshness_alerts(scheme_code) WHERE resolved_at IS NULL;
CREATE INDEX idx_mf_active_alerts ON mutual_fund_freshness_alerts(expected_nav_date) WHERE resolved_at IS NULL;
