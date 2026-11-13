# Mutual fund historical NAV import

The read-only NAV history workflow accepts an authorized local CSV with exactly these columns:

```csv
scheme_code,as_of,nav
12345,2025-01-01,10.0
12345,2025-01-31,10.5
```

Open the **Mutual Funds** workspace, paste the CSV and provide the exact scheme code, scheme name and source name. ATLAS validates strictly increasing ISO dates, positive finite NAVs, a single exact scheme code and at most 4,000 rows. It returns latest NAV, freshness and trailing returns where history is sufficient. Results are not persisted, automatically sourced, used to reprice holdings or represented as independently verified.

API: POST `/api/v1/intelligence/mutual-funds/nav-history-import` with `scheme_code`, `scheme_name`, `source_name` and `csv_text`. Input is limited to 500,000 characters. Errors are sanitized. Data is not an independently verified provider feed. Annualized figures are historical mathematical observations, not forecasts.

Outstanding production integrations: verified lawful provider retrieval, authenticated persistent fund master and scheme mapping, total-return adjustments, benchmarking, and portfolio valuation reconciliation. These must not be represented as complete without real source data and entitlement checks.
