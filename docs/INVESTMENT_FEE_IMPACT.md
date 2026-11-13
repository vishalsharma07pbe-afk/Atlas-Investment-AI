# Investment Costs & Fee Impact Analysis

A complete read-only module comprising a Python fee model, POST API, dashboard form, yearly checkpoints, Python tests and Vitest tests.

## Use

Open **My Portfolio → Investment fees & compounding**. Enter starting balance, monthly contributions, duration, hypothetical gross annual return, annual expense ratio, contribution charge and monthly flat fee. Click **Calculate fee impact**.

API: `POST /api/v1/intelligence/planning/fee-impact`

Example request:
```json
{"initial_amount":"100000","monthly_contribution":"10000","months":36,"annual_return_percent":"8","annual_expense_ratio_percent":"1","contribution_fee_percent":"0","monthly_flat_fee":"0"}
```

The calculator models monthly compounding at annual gross return / 12. Each month: gross return accrues on the previous balance, expense ratio / 12 is deducted from the post-return balance, a contribution fee is deducted from the end-of-month contribution, and a flat fee is deducted from the available balance (never below zero). The no-fee comparator uses identical principal and return assumptions. Annual checkpoints show both balances and their difference.

**Fee drag is not equal to summed charges** because foregone future compounding also contributes to the difference. The model does not include GST, brokerage-specific taxes, exit loads, fund-specific charging conventions, regulatory rates, inflation or changing market returns. Input values are illustrative assumptions, not verified fees or forecasts. No account access, order placement or live market data is involved.
