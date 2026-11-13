# Mutual fund valuation reconciliation

POST `/api/v1/intelligence/mutual-funds/reconcile` with explicitly mapped `positions` (holding_id, scheme_code, units, invested, optional recorded_value) and `navs` (scheme_code, nav, as_of, source_name). NAVs must come from a source the user is authorized to use.

Reconciliation uses exact scheme-code matching only. It returns source-attributed per-position estimates, differences from recorded values, missing and stale NAV warnings, and an aggregate estimate **only if every position has a NAV no older than seven days and all matched NAVs share the same valuation date**. Missing and stale positions never receive invented values. Mixed NAV dates prevent a synchronized portfolio total. The operation is read-only and never changes the portfolio database.

This is a valuation estimate, not a verified provider feed, investment recommendation, NAV forecast or automated market-data import. Recorded values remain independent. For production, scheme mapping must be independently confirmed and provider access/rights verified.
