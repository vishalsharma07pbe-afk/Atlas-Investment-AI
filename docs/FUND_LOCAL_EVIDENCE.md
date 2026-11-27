# Authorized local fund evidence

Official pages:
- NSE Indices historical data: https://www.niftyindices.com/reports/historical-data (Total returns Index Values, gross TRI column, not price or net TRI).
- AMFI TER: https://www.amfiindia.com/ter-of-mf-schemes
- AMFI data/disclosure navigation: https://www.amfiindia.com/research-information/amfi-data

No supported automated contract has been verified. This is a local **operator-normalized** input, not an authenticated download or an automatic official data feed. Only use exports for which usage rights are confirmed. Do not enter invented values. Retain original publisher files outside this normalized evidence file. Verify exact Direct Growth AMFI code/ISIN and current benchmark yourself. Historical benchmark changes are not verified.

Set ATLAS_MF_LOCAL_EVIDENCE_ENABLED=true and MARKET_DATA_USAGE_RIGHTS_CONFIRMED=true only if authorized. Put data/fund-evidence/evidence.json in the local repo (do not commit actual licensed files). Compose mounts the folder read-only. On every category dashboard/scheduled refresh, validated data is read automatically. Missing or invalid data is withheld. Existing qualification gates unchanged.

Schema (field definitions, not sample data):
- schema: "MF-LOCAL-TRI-1"
- authorization_attested: true
- indices: array of {benchmark, source_url, series_type, observations}; exact uppercase names from INDEXES in fund_local_evidence.py; source_url fixed NSE historical page, series_type GROSS_TOTAL_RETURN_INDEX. Observations are {date: YYYY-MM-DD, tri: positive numeric value} in strict ascending order, 157–2000 per index, no duplicates.
- schemes: array of {scheme_code: integer, isin_growth, plan: DIRECT, option: GROWTH, benchmark, source_url: AMFI data page, ter_source_url: AMFI TER page, disclosure_date, ter_date, ter_percent: numeric percent, riskometer, riskometer_date}. All dates ISO, no future dates. Maximum 1000 schemes; distinct codes and ISINs. Riskometer enum in code.

Matched comparisons require all 157 exact observed NAV dates in supplied TRI, original anchor digest, same scheme identity, current disclosure <=60 days. TER older than 90 days and Riskometer older than 60 days are separately withheld. One/three-year annualized comparisons, 105 overlapping rolling years, relative return differences and weekly active volatility are descriptive. Segment proxy uses Nifty 100, Midcap 150 and Smallcap 250 TRI; not a fund's actual benchmark. No rating, forward estimate, qualification, or automatic trade.

## Scheduled authorized gross TRI CSV sources

Set `ATLAS_MF_OFFICIAL_TRI_ENABLED=true` only with confirmed rights and a verified direct HTTPS CSV contract on `www.niftyindices.com` or `niftyindices.com`. Put `tri-sources.json` alongside `evidence.json` with `schema` = `NSE-TRI-CSV-1`, `authorization_attested` = true, and `sources` = a list of `{benchmark,url}`. Benchmark must be an exact supported TRI name; URL must be an actual authorized direct CSV URL, not the interactive report page. No default endpoints are guessed. The published historical report distinguishes gross and net TRI; supported CSV headers are `IndexName,Date,Total Returns Index` with optional `Net Total Return Index`. Current publisher CSV transport and exact downloaded schema remain subject to live acceptance. One bounded request per due pass, six-hour per-series refresh, 48-hour cache age and seven-day latest observation checks. No redirects or credentials. Local and downloaded series are not spliced; contradictory overlaps withhold the index. Current fund benchmark mapping still requires exact authorized scheme evidence. No promotion of qualification gates.
