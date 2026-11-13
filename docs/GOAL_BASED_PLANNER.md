# Goal-Based Investment Planner

This is a complete, self-contained planning module (Python engine, validated API, React UI, Python/Vitest tests).

## How to use

In **My Portfolio**, open **Goal-based investment planner** and enter a target amount in INR, starting savings, monthly contribution, horizon in months (1–600), and an assumed annual return (-30% to +30%). Click **Calculate goal**. ATLAS shows the hypothetical end balance, principal, assumed growth, shortfall, required monthly contribution from the beginning, and annual checkpoints.

API: `POST /api/v1/intelligence/planning/goal-projection`

Example request:

```json
{"target_amount":"1000000","initial_amount":"50000","monthly_contribution":"10000","months":36,"annual_return_percent":"8"}
```

The model applies the supplied nominal annual rate divided by 12, compounds monthly, and adds contributions at the **end** of each month. The minimum required monthly amount is rounded upward to the next paisa. Checkpoints are generated at each 12-month interval and the final month. Calculations are stateless: goals are not saved to a server or brokerage account.

**Limitations:** A fixed return is a user-supplied assumption, not an expected market return or probability. The model excludes inflation, fees, taxes, irregular contributions, real-world volatility and capital loss beyond the chosen fixed negative rate. It is not a recommendation to buy a particular fund, stock or asset, and does not fetch market data or place orders.
