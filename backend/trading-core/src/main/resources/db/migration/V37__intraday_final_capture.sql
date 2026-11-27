-- Persist final-session request claims, bounded independently of open-market polling.
CREATE TABLE intraday_final_capture (
 instrument_id BIGINT NOT NULL REFERENCES instruments(id) ON DELETE CASCADE,
 session_date DATE NOT NULL, attempts INTEGER NOT NULL CHECK(attempts BETWEEN 1 AND 2),
 next_attempt_at TIMESTAMPTZ NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('RUNNING','COMPLETE','MISSING_FINAL_BAR','FAILED')),
 PRIMARY KEY(instrument_id,session_date)
);
