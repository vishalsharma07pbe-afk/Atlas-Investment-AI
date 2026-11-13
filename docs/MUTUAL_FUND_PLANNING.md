# Mutual Fund Intelligence — integrated planning

The Mutual Funds workspace combines manual NAV import, historical analysis, fund comparison, valuation reconciliation, refresh preflight and export with **SIP planning and recorded-portfolio allocation**.

## SIP planning
POST `/api/v1/intelligence/mutual-funds/plan` with `sip` containing `monthly_contribution`, `annual_return_pct`, `years`, optional `annual_step_up_pct` and `initial_amount`, plus optional `positions` with holding ID, label, invested amount and nullable recorded value. The calculation assumes beginning-of-month payments, an effective monthly rate derived from the assumed annual return, and an annual SIP increase at the start of each subsequent year. Returns are hypothetical, not forecasts; fees, taxes and inflation are excluded.

## Portfolio allocation
The dashboard uses recorded values from saved fund holdings. Unpriced positions are excluded from allocation weights and the total portfolio valuation is marked incomplete. Concentration is reported as the largest weight among priced holdings. No NAV feed, fund category, benchmark, expense ratio or overlap is invented.

## Boundaries
All computations are read-only and user-data-dependent. Provider-backed NAV ingestion, independently verified scheme directories, benchmarks, fund holdings overlap and personalized investment recommendations remain unavailable until trustworthy data and permissions are established. This implementation does not constitute a complete production fund-data platform.

## Goal-based SIP planning

POST `/api/v1/intelligence/mutual-funds/goal-plan` with `target_amount`, `years`, `annual_return_pct`, optional `annual_step_up_pct`, `initial_amount` and `current_monthly_sip`. The endpoint calculates a rounded-up whole-rupee monthly SIP using the same beginning-of-month and annual-step-up assumptions as the SIP planner, and compares the user's current plan with the target. It returns required SIP, incremental SIP, current-plan projected shortfall and annual snapshots. The dashboard exposes this in **Monthly SIP required for your goal**. It does not save a goal or recommend funds; the assumed return is not guaranteed.
