# Mutual fund NAV data-quality diagnostics

The read-only reconciliation API now includes `diagnostics` and `quality_summary` in addition to existing results. Each diagnostic includes a stable code, severity, count and message.

- BLOCKER: MISSING_NAV, STALE_NAV (older than seven days), and MIXED_AS_OF_DATES. These prevent a complete synchronized aggregate portfolio estimate.
- WARNING: UNVERIFIED_PROVENANCE. Named sources are user-supplied, not independently verified.
- INFO: MULTIPLE_SOURCES, UNUSED_NAV_CODES, NO_RECORDED_VALUE.

The Mutual Funds dashboard displays these diagnostics alongside estimated vs recorded values. Mixed NAV dates now block a complete aggregate estimate. Partial matched-position estimates remain available and must not be interpreted as a synchronized end-of-day portfolio valuation.

No automatic provider retrieval, independent scheme verification, source-rights assertion, persistent writes, or portfolio repricing is performed. Use the quality summary to decide whether a supplied NAV snapshot is sufficiently complete for research, not for execution.
