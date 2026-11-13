# Mutual fund historical NAV comparison

POST `/api/v1/intelligence/mutual-funds/compare` with `{"funds":[{scheme_code,scheme_name,source_name,csv_text},...]}`, using 2–5 distinct schemes. Each fund must have its own source-attributed NAV history in CSV format (`scheme_code,as_of,nav`).

The response includes source provenance, latest NAV date, staleness and trailing returns for each fund. When latest dates differ, the comparison is explicitly flagged as non-aligned. No fabricated ratings, benchmarks or rankings are returned. No data is persisted or used to reprice holdings.

**Limitations:** comparisons are observational, not total-return adjusted; no dividend reinvestment, loads, taxes, risk-adjusted measures, or portfolio allocation are inferred. This is not an automated licensed NAV feed.
