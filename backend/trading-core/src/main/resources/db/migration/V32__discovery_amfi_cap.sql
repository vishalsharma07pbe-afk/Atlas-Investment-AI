-- Shared public AMFI evidence. Never store personal holdings or credentials.
CREATE TABLE discovery_amfi_cap (
 isin VARCHAR(12) PRIMARY KEY CHECK(isin ~ '^IN[A-Z0-9]{9}[0-9]$'),
 category VARCHAR(12) NOT NULL CHECK(category IN ('LARGE_CAP','MID_CAP','SMALL_CAP')),
 average_cap_cr NUMERIC NOT NULL CHECK(average_cap_cr>0 AND average_cap_cr<100000000),
 as_of DATE NOT NULL CHECK((extract(month FROM as_of)=6 AND extract(day FROM as_of)=30) OR
                            (extract(month FROM as_of)=12 AND extract(day FROM as_of)=31)),
 received_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE VIEW discovery_cap_coverage AS
SELECT u.exchange,coalesce(c.category,'UNKNOWN') category,c.as_of,
 count(*) AS mapped_listings,count(DISTINCT u.isin) AS distinct_companies
FROM discovery_quote_universe u LEFT JOIN discovery_amfi_cap c ON c.isin=u.isin
 AND c.as_of BETWEEN (now() AT TIME ZONE 'Asia/Kolkata')::date-220 AND (now() AT TIME ZONE 'Asia/Kolkata')::date-1
GROUP BY u.exchange,c.category,c.as_of;
