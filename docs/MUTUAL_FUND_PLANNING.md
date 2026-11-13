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

## Recorded-value concentration diagnostics

POST `/api/v1/intelligence/mutual-funds/portfolio-risk` with a non-empty list of holdings containing unique holding IDs, labels and nullable recorded values. The dashboard displays largest position weight, top-three weight, the Herfindahl-Hirschman concentration index (HHI, 0–10,000), and effective number of fund positions (1/sum of squared fund-position weights). Missing recorded values block full-portfolio conclusions. Zero total recorded value produces no invented weights. These are **fund-position concentration statistics**, not volatility estimates, risk ratings, sector allocation or underlying-security overlap. Those require verified underlying holdings and return histories.

## Historical NAV return and drawdown diagnostics

POST `/api/v1/intelligence/mutual-funds/historical-risk` with a numeric `scheme_code`, `source_name`, and 2–4000 chronologically increasing `observations` containing `as_of` and positive finite `nav`. The Mutual Funds workspace accepts a two-column `as_of,nav` CSV and renders cumulative NAV change, annualized NAV change and maximum observed peak-to-trough drawdown. Annualized sample volatility is shown only when every NAV observation is exactly one calendar day apart and at least three observations exist; irregular or insufficient history returns an explicit unavailable status. NAV-only changes are not investor total returns; missing dates, dividends, fees, taxes and fund risk classifications are not inferred.

## Connected historical NAV workflow

In the Mutual Funds workspace, enter the exact scheme code, name, source and three-column NAV CSV in **Import fund history and calculate returns**. After a successful server validation, the **Drawdown & return risk** panel exposes **Analyze validated import** and reuses the same dated NAV observations without a second manual entry. A new import attempt clears the previously validated batch, preventing stale history from being presented as the current import. All data remains in browser component state for the session and is sent to the existing read-only API for calculations; it is not saved as fund holdings or fetched from an external provider. An integrated React test covers import, transfer and historical risk request.
