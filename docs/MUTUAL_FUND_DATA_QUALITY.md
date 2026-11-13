# Mutual fund NAV data-quality diagnostics

The read-only reconciliation API now includes `diagnostics` and `quality_summary` in addition to existing results. Each diagnostic includes a stable code, severity, count and message.

- BLOCKER: MISSING_NAV and STALE_NAV (older than seven days). These prevent a complete aggregate portfolio estimate.
- WARNING: MIXED_AS_OF_DATES and UNVERIFIED_PROVENANCE. Mixed dates mean holdings are valued at different observation dates; named sources are user-supplied, not independently verified.
- INFO: MULTIPLE_SOURCES, UNUSED_NAV_CODES, NO_RECORDED_VALUE.

The Mutual Funds dashboard displays these diagnostics alongside estimated vs recorded values. Mixed dates are warned about but do not independently block the existing aggregate estimate; users should not interpret that aggregate as a synchronized end-of-day valuation.

No automatic provider retrieval, independent scheme verification, source-rights assertion, persistent writes, or portfolio repricing is performed. Use the quality summary to decide whether a supplied NAV snapshot is sufficiently complete for research, not for execution.
