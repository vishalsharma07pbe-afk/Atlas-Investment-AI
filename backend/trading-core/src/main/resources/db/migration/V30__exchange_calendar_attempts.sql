CREATE TABLE exchange_calendar_attempts(
 session_date DATE PRIMARY KEY,
 status VARCHAR(24) NOT NULL CHECK(status IN ('RUNNING','SUCCESS','WAITING_EVIDENCE','FAILED')),
 claim_id UUID,
 attempted_at TIMESTAMPTZ NOT NULL,
 next_attempt_at TIMESTAMPTZ NOT NULL,
 rows_written INT NOT NULL DEFAULT 0 CHECK(rows_written>=0),
 error_code VARCHAR(80)
);
CREATE INDEX idx_exchange_calendar_attempts_due ON exchange_calendar_attempts(next_attempt_at,session_date);
