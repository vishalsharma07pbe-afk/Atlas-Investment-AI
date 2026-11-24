-- Public-market research only. No holding ownership or broker credentials are copied.
CREATE TABLE discovery_history_attempts (
  instrument_id BIGINT PRIMARY KEY REFERENCES instruments(id) ON DELETE CASCADE,
  attempted_at TIMESTAMPTZ NOT NULL,
  next_attempt_at TIMESTAMPTZ NOT NULL,
  status VARCHAR(12) NOT NULL CHECK(status IN ('RUNNING','SUCCESS','FAILED')),
  rows_written INTEGER NOT NULL DEFAULT 0 CHECK(rows_written>=0)
);
CREATE INDEX idx_discovery_history_due ON discovery_history_attempts(next_attempt_at);
CREATE INDEX idx_upstox_discovery_mapping ON upstox_instrument_map(exchange_code,trading_symbol);
