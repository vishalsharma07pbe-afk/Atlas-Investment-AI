
-- Public, operator-authorized market observations only; never portfolio/account data.
CREATE VIEW discovery_quote_universe AS
SELECT i.id AS instrument_id,e.code AS exchange,i.isin,i.symbol,m.instrument_key
FROM instruments i JOIN exchanges e ON e.id=i.exchange_id
JOIN LATERAL (
 SELECT min(instrument_key) AS instrument_key
 FROM upstox_instrument_map
 WHERE exchange_code=e.code AND trading_symbol=i.symbol AND isin=i.isin
 AND instrument_type IN ('EQ','EQUITY')
 AND (instrument_key=e.code||'_EQ|'||i.isin
      OR (e.code='BSE' AND instrument_key ~ '^BSE_EQ[|][0-9]{1,10}$'))
 HAVING count(*)=1
) m ON true
WHERE e.code IN ('NSE','BSE') AND i.active AND i.listing_status='ACTIVE'
 AND i.series='EQ' AND i.instrument_type IN ('EQ','EQUITY','STOCK')
 AND i.isin ~ '^INE[A-Z0-9]{8}[0-9]$'
 AND (i.delisted_on IS NULL OR i.delisted_on>(now() AT TIME ZONE 'Asia/Kolkata')::date)
 AND (i.listed_on IS NULL OR i.listed_on<=(now() AT TIME ZONE 'Asia/Kolkata')::date);

CREATE TABLE discovery_quote_screen(
 instrument_id BIGINT PRIMARY KEY REFERENCES instruments(id),
 instrument_key TEXT NOT NULL,
 isin VARCHAR(12) NOT NULL,
 attempted_at TIMESTAMPTZ NOT NULL,
 state VARCHAR(24) NOT NULL CHECK(state IN ('PENDING','PRIORITY','OBSERVED','MISSING','INVALID','FAILED')),
 observed_at TIMESTAMPTZ,
 response_at TIMESTAMPTZ,
 last_price NUMERIC CHECK(last_price>0),
 previous_close NUMERIC CHECK(previous_close>0),
 session_volume BIGINT CHECK(session_volume>=0),
 turnover_proxy NUMERIC CHECK(turnover_proxy>=0),
 spread_percent NUMERIC CHECK(spread_percent>=0),
 day_change_percent NUMERIC,
 CHECK ((state IN ('PRIORITY','OBSERVED'))=(observed_at IS NOT NULL AND response_at IS NOT NULL AND last_price IS NOT NULL))
);
CREATE INDEX idx_discovery_quote_attempt ON discovery_quote_screen(attempted_at);
CREATE VIEW discovery_quote_coverage AS
SELECT u.exchange,count(*) AS mapped_listings,count(q.instrument_id) AS attempted_listings,
 count(*) FILTER(WHERE q.state IN ('PRIORITY','OBSERVED') AND q.observed_at>=now()-interval '15 minutes' AND q.response_at>=now()-interval '15 minutes') AS recent_observations,
 count(*) FILTER(WHERE q.state='PRIORITY' AND q.observed_at>=now()-interval '15 minutes' AND q.response_at>=now()-interval '15 minutes') AS recent_priority,
 count(*) FILTER(WHERE q.state IN ('MISSING','INVALID','FAILED')) AS last_attempt_unusable,
 max(q.attempted_at) AS latest_attempt
FROM discovery_quote_universe u LEFT JOIN discovery_quote_screen q
 ON q.instrument_id=u.instrument_id AND q.instrument_key=u.instrument_key AND q.isin=u.isin
GROUP BY u.exchange;
