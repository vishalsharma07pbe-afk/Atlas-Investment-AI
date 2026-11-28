-- Dated provider classifications are observations, never a trade authorization.
ALTER TABLE upstox_instrument_map ADD COLUMN security_type VARCHAR(12) NOT NULL DEFAULT 'UNKNOWN'
  CHECK(security_type IN ('NORMAL','SME','RELIST','PCA','IPO','UNKNOWN')),
  ADD COLUMN security_observed_at TIMESTAMPTZ;

CREATE TABLE discovery_suspension_snapshot(
 singleton BOOLEAN PRIMARY KEY CHECK(singleton),
 retrieved_at TIMESTAMPTZ NOT NULL,
 record_count INTEGER NOT NULL CHECK(record_count>=0)
);
CREATE TABLE discovery_suspended_listing(
 exchange VARCHAR(10) NOT NULL CHECK(exchange IN ('NSE','BSE')),
 isin VARCHAR(12) NOT NULL CHECK(isin ~ '^INE[A-Z0-9]{8}[0-9]$'),
 instrument_key TEXT NOT NULL,
 PRIMARY KEY(exchange,isin,instrument_key)
);
CREATE VIEW discovery_security_context AS
 SELECT u.instrument_id,u.exchange,u.isin,u.instrument_key,
 CASE WHEN s.retrieved_at BETWEEN now()-interval '72 hours' AND now() AND l.instrument_key IS NOT NULL THEN 'SUSPENDED_REPORTED'
      WHEN m.security_observed_at BETWEEN now()-interval '72 hours' AND now() THEN m.security_type
      ELSE 'UNKNOWN' END AS security_state,
 CASE WHEN s.retrieved_at BETWEEN now()-interval '72 hours' AND now() AND l.instrument_key IS NOT NULL THEN s.retrieved_at
      WHEN m.security_observed_at BETWEEN now()-interval '72 hours' AND now() THEN m.security_observed_at END AS security_evidence_at
 FROM discovery_quote_universe u JOIN upstox_instrument_map m ON m.instrument_key=u.instrument_key AND m.isin=u.isin
 LEFT JOIN discovery_suspension_snapshot s ON s.singleton
 LEFT JOIN discovery_suspended_listing l ON l.exchange=u.exchange AND l.isin=u.isin AND l.instrument_key=u.instrument_key;
CREATE VIEW discovery_security_coverage AS
 SELECT exchange,security_state,count(*) AS mapped_listings,max(security_evidence_at) AS latest_evidence
 FROM discovery_security_context GROUP BY exchange,security_state;
