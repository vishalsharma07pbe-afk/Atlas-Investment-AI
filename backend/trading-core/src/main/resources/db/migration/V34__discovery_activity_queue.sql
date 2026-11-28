-- Last valid observed intraday activity; never substitute this for a daily candle.
CREATE TABLE discovery_activity_day(
 instrument_id BIGINT NOT NULL REFERENCES instruments(id),
 instrument_key TEXT NOT NULL,
 isin VARCHAR(12) NOT NULL,
 session_date DATE NOT NULL,
 observed_at TIMESTAMPTZ NOT NULL,
 response_at TIMESTAMPTZ NOT NULL,
 session_volume BIGINT NOT NULL CHECK(session_volume>0),
 turnover_proxy NUMERIC NOT NULL CHECK(turnover_proxy>0),
 spread_percent NUMERIC CHECK(spread_percent>=0),
 day_change_percent NUMERIC NOT NULL,
 late_session BOOLEAN NOT NULL,
 PRIMARY KEY(instrument_id,session_date),
 CHECK(session_date=(observed_at AT TIME ZONE 'Asia/Kolkata')::date),
 CHECK(response_at>=observed_at)
);
CREATE INDEX idx_discovery_activity_retention ON discovery_activity_day(session_date);
-- Dated acquisition hints, not investment suitability or execution eligibility.
-- A missing observation, missing cap or missing classification is not a negative finding.
CREATE VIEW discovery_candidate_queue AS
 WITH evidence AS (
 SELECT u.instrument_id,u.exchange,u.instrument_key,u.isin,
   coalesce(c.category,'UNKNOWN') AS category,c.average_cap_cr,c.as_of AS cap_as_of,
   coalesce(s.security_state,'UNKNOWN') AS security_state,
   a.session_date AS activity_session,a.observed_at,a.response_at,a.turnover_proxy,a.spread_percent,a.day_change_percent,
   coalesce(l.n,0) AS observed_late_sessions,coalesce(l.low,0) AS low_late_sessions,
   CASE c.category WHEN 'LARGE_CAP' THEN 50000000::numeric WHEN 'MID_CAP' THEN 20000000::numeric
       WHEN 'SMALL_CAP' THEN 10000000::numeric ELSE 50000000::numeric END AS swing_floor
 FROM discovery_quote_universe u
 LEFT JOIN discovery_security_context s ON s.instrument_id=u.instrument_id AND s.instrument_key=u.instrument_key AND s.isin=u.isin
 LEFT JOIN discovery_amfi_cap c ON c.isin=u.isin
   AND c.as_of BETWEEN (now() AT TIME ZONE 'Asia/Kolkata')::date-220 AND (now() AT TIME ZONE 'Asia/Kolkata')::date-1
 LEFT JOIN LATERAL (
  SELECT d.* FROM discovery_activity_day d
  WHERE d.instrument_id=u.instrument_id AND d.instrument_key=u.instrument_key AND d.isin=u.isin
    AND d.session_date BETWEEN (now() AT TIME ZONE 'Asia/Kolkata')::date-4 AND (now() AT TIME ZONE 'Asia/Kolkata')::date
    AND d.observed_at<=now() AND d.response_at<=now()
  ORDER BY d.session_date DESC LIMIT 1
 ) a ON true
 LEFT JOIN LATERAL (
  SELECT count(*) n,count(*) FILTER (WHERE z.turnover_proxy<2500000) low
  FROM (
   SELECT d.turnover_proxy FROM discovery_activity_day d
   WHERE d.instrument_id=u.instrument_id AND d.instrument_key=u.instrument_key AND d.isin=u.isin AND d.late_session
     AND d.session_date BETWEEN (now() AT TIME ZONE 'Asia/Kolkata')::date-10 AND (now() AT TIME ZONE 'Asia/Kolkata')::date
     AND d.observed_at<=now() AND d.response_at<=now()
   ORDER BY d.session_date DESC LIMIT 5
  ) z
 ) l ON true
 ), flags AS (
 SELECT *,
   observed_late_sessions>=3 AND low_late_sessions=observed_late_sessions AS repeated_low_activity,
   security_state IN ('NORMAL','UNKNOWN') AND (average_cap_cr IS NULL OR average_cap_cr>=1000) AS standard_research,
   coalesce(observed_at>=now()-interval '15 minutes' AND response_at>=now()-interval '15 minutes'
       AND activity_session=(now() AT TIME ZONE 'Asia/Kolkata')::date,false) AS fresh_activity
 FROM evidence
 ), hints AS (
 SELECT *,
   coalesce(standard_research AND NOT repeated_low_activity AND fresh_activity AND average_cap_cr>=1000
       AND turnover_proxy>=swing_floor*2 AND spread_percent<=0.5 AND abs(day_change_percent)<10,false) AS intraday_activity_hint,
   coalesce(standard_research AND NOT repeated_low_activity AND average_cap_cr>=1000
       AND turnover_proxy>=swing_floor AND spread_percent<=0.75 AND abs(day_change_percent)<10,false) AS swing_activity_hint,
   coalesce(standard_research AND NOT repeated_low_activity AND average_cap_cr>=1000
       AND turnover_proxy>=swing_floor/2 AND spread_percent<=1 AND abs(day_change_percent)<10,false) AS short_term_activity_hint,
   coalesce(standard_research AND average_cap_cr>=1000 AND turnover_proxy>=2500000,false) AS long_term_research_hint,
   coalesce(standard_research AND average_cap_cr IS NULL AND NOT repeated_low_activity
       AND turnover_proxy>=10000000 AND spread_percent<=1 AND abs(day_change_percent)<10,false) AS unclassified_activity_hint
 FROM flags
 )
 SELECT *,
   CASE WHEN security_state='SUSPENDED_REPORTED' THEN 'SUSPENDED_REPORTED'
        WHEN security_state NOT IN ('NORMAL','UNKNOWN') THEN 'SPECIAL_CLASSIFICATION_REVIEW'
        WHEN average_cap_cr<1000 THEN 'BELOW_STANDARD_CAP_FLOOR'
        WHEN repeated_low_activity THEN 'REPEATED_LOW_ACTIVITY_REVIEW'
        WHEN activity_session IS NULL THEN 'AWAITING_ACTIVITY'
        WHEN intraday_activity_hint OR swing_activity_hint OR short_term_activity_hint THEN 'ACTIVE_RESEARCH_PRIORITY'
        WHEN long_term_research_hint THEN 'LONG_TERM_RESEARCH_PRIORITY'
        WHEN unclassified_activity_hint THEN 'CAP_EVIDENCE_REQUIRED'
        ELSE 'OBSERVED_ACTIVITY_ONLY' END AS queue_state,
   CASE WHEN intraday_activity_hint THEN 5 WHEN swing_activity_hint THEN 4
        WHEN short_term_activity_hint THEN 3 WHEN long_term_research_hint THEN 2
        WHEN unclassified_activity_hint THEN 1 ELSE 0 END AS priority
 FROM hints;
CREATE VIEW discovery_candidate_coverage AS
 SELECT exchange,category,queue_state,count(*) AS mapped_listings,
  count(*) FILTER (WHERE intraday_activity_hint) AS intraday_hints,
  count(*) FILTER (WHERE swing_activity_hint) AS swing_hints,
  count(*) FILTER (WHERE short_term_activity_hint) AS short_term_hints,
  count(*) FILTER (WHERE long_term_research_hint) AS long_term_hints,
  count(*) FILTER (WHERE security_state='UNKNOWN') AS unknown_classification,
  max(activity_session) AS latest_activity_session
 FROM discovery_candidate_queue GROUP BY exchange,category,queue_state;
