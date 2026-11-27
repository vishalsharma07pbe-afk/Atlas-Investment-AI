-- Public market research only: no account, position, credential or order columns.
CREATE TABLE intraday_scenario_watch (
 session_date DATE NOT NULL, isin VARCHAR(12) NOT NULL CHECK(isin ~ '^INE[A-Z0-9]{9}$'),
 instrument_id BIGINT NOT NULL REFERENCES instruments(id) ON DELETE RESTRICT,
 exchange VARCHAR(10) NOT NULL CHECK(exchange IN ('NSE','BSE')), symbol VARCHAR(50) NOT NULL,
 published_at TIMESTAMPTZ NOT NULL, expiry TIMESTAMPTZ NOT NULL CHECK(expiry>published_at),
 evidence JSONB NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING','OBSERVED_CASES','EVIDENCE_GAP')),
 outcome JSONB, PRIMARY KEY(session_date,isin)
);
CREATE INDEX intraday_scenario_due ON intraday_scenario_watch(expiry) WHERE status='PENDING';
CREATE FUNCTION protect_intraday_scenario_watch() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.status<>'PENDING' OR (NEW.session_date,NEW.isin,NEW.instrument_id,NEW.exchange,NEW.symbol,NEW.published_at,NEW.expiry,NEW.evidence)
 IS DISTINCT FROM (OLD.session_date,OLD.isin,OLD.instrument_id,OLD.exchange,OLD.symbol,OLD.published_at,OLD.expiry,OLD.evidence) THEN
  RAISE EXCEPTION 'immutable intraday scenario evidence';
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER intraday_scenario_immutable BEFORE UPDATE ON intraday_scenario_watch
 FOR EACH ROW EXECUTE FUNCTION protect_intraday_scenario_watch();
CREATE TABLE intraday_scenario_replay (
 session_date DATE NOT NULL, instrument_id BIGINT NOT NULL REFERENCES instruments(id) ON DELETE RESTRICT,
 isin VARCHAR(12) NOT NULL, exchange VARCHAR(10) NOT NULL, captured_at TIMESTAMPTZ NOT NULL,
 outcome JSONB NOT NULL, PRIMARY KEY(session_date,instrument_id)
);
