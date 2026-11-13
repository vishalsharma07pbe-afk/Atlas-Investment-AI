# Mutual fund NAV data-quality diagnostics

The read-only reconciliation API now includes `diagnostics` and `quality_summary` in addition to existing results. Each diagnostic includes a stable code, severity, count and message.

- BLOCKER: MISSING_NAV, STALE_NAV (older than seven days), and MIXED_AS_OF_DATES. These prevent a complete synchronized aggregate portfolio estimate.
- WARNING: UNVERIFIED_PROVENANCE. Named sources are user-supplied, not independently verified.
- INFO: MULTIPLE_SOURCES, UNUSED_NAV_CODES, NO_RECORDED_VALUE.

The Mutual Funds dashboard displays these diagnostics alongside estimated vs recorded values. Mixed NAV dates now block a complete aggregate estimate. Partial matched-position estimates remain available and must not be interpreted as a synchronized end-of-day portfolio valuation.

No automatic provider retrieval, independent scheme verification, source-rights assertion, persistent writes, or portfolio repricing is performed. Use the quality summary to decide whether a supplied NAV snapshot is sufficiently complete for research, not for execution.

## Selected-scheme snapshot validation

Selected scheme codes must use ASCII digits. A selected scheme row with missing columns is rejected rather than silently ignored. Duplicate selected codes are excluded even when one of their rows is malformed. Positive finite Decimal NAVs that overflow the JSON floating-point representation are rejected before response serialization. The snapshot response exposes `duplicate_scheme_codes` and `rejected_rows`; integrated portfolio review blocks on rejected selected rows. Malformed unselected rows are not treated as portfolio coverage errors. These checks do not verify the source or authorize trading.
