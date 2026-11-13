# Portfolio Allocation & Contribution Planner

This module adds a complete read-only planning workflow to **My Portfolio**: a Python calculation engine, validated POST API, React form/results table, unit tests and UI tests.

## Workflow

1. Record holdings and optional last prices/NAVs in the existing local portfolio workspace.
2. Open **Allocation & contribution planner** and enter an additional INR contribution.
3. Specify asset-type targets that total exactly 100%, e.g. `EQUITY` and `MUTUAL_FUND` (use asset types matching your holdings).
4. Select **Calculate hypothetical allocation**. The result shows current weights, target weights, a cash-only hypothetical allocation and remaining target gaps.

API: `POST /api/v1/intelligence/portfolio/allocation-plan` with `{"contribution":"10000","targets":[{"asset_type":"EQUITY","weight_percent":"70"},{"asset_type":"MUTUAL_FUND","weight_percent":"30"}]}`.

The engine uses **only locally recorded last prices**. Holdings without a price are explicitly excluded and reported. Targets must be unique, uppercase asset types, and sum to exactly 100%. No recorded positive value returns `NO_PRICED_VALUE` instead of fabricated weights. Contributions are distributed proportionally among positive target-value deficits; it never recommends selling existing positions. Paise-level rounding differences may appear.

This is hypothetical arithmetic, **not a trade recommendation, live market valuation, tax-aware rebalance, order placement or forecast**. Actual prices, costs, risk, tax treatment and suitability need separate verification. No broker or exchange connection is initiated.

Tests: Python unit tests under `intelligence/tests/test_portfolio_allocation.py` and React/Vitest tests under `frontend/trading-dashboard/src/PortfolioAllocation.test.tsx`.
