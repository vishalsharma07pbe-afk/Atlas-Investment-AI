CREATE TABLE intraday_research_attempts (
 instrument_id BIGINT PRIMARY KEY REFERENCES instruments(id) ON DELETE CASCADE,
 attempted_at TIMESTAMPTZ NOT NULL,
 next_attempt_at TIMESTAMPTZ NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('RUNNING','SUCCESS','FAILED'))
);
