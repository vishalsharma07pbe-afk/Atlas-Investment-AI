# Mutual fund NAV research (read-only)

The NAV research endpoint accepts user-supplied, source-attributed historical daily NAVs. No external feed or licensed AMFI source is claimed. Data is not persisted and no market value is overwritten.

POST `/api/v1/intelligence/mutual-funds/nav-analysis` with JSON:
```json
{"scheme_code":"12345","scheme_name":"Example Fund Direct Growth","source_name":"User-provided NAV file","navs":[{"as_of":"2025-01-01","nav":10.0},{"as_of":"2025-01-31","nav":10.5}]}
```

Dates must be unique and ascending, NAVs positive and finite, and future dates disallowed. Results report source provenance as USER_SUPPLIED_UNVERIFIED. Returns are calculated only when a sufficiently close historical NAV exists. For 1m/3m/6m simple returns are used; 1y/3y/5y use CAGR. NAVs are not real-time stock prices; distributions, taxes and loads are excluded. Fund ratings are not fabricated.

**Not yet available:** automated authorized NAV acquisition, AMFI scheme master mapping, provider-verified ratings, dividends-adjusted total return or benchmark comparisons. Do not use this as investment advice.
