-- Track automatic public NAV history requests without modifying holdings.
CREATE TABLE fund_history_attempts (
  scheme_code BIGINT PRIMARY KEY REFERENCES mutual_fund_schemes(scheme_code) ON DELETE CASCADE,
  attempted_at TIMESTAMPTZ NOT NULL,
  next_attempt_at TIMESTAMPTZ NOT NULL,
  status VARCHAR(12) NOT NULL CHECK(status IN ('RUNNING','SUCCESS','FAILED'))
);
