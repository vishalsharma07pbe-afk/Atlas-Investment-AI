# Goal Scenario Comparison

Use the **Compare savings scenarios** panel in **My Portfolio** to compare 2–5 hypothetical savings plans. Enter a common target and starting balance, then independently edit each scenario's name, monthly contribution, horizon and assumed annual return. Click **Compare scenarios** to see projected value, contributed principal, target shortfall and monthly amount needed for the selected horizon.

API: `POST /api/v1/intelligence/planning/goal-comparison`

Example:
```json
{"scenarios":[
  {"name":"Base","parameters":{"target_amount":"1000000","initial_amount":"0","monthly_contribution":"10000","months":36,"annual_return_percent":"8"}},
  {"name":"Higher SIP","parameters":{"target_amount":"1000000","initial_amount":"0","monthly_contribution":"15000","months":36,"annual_return_percent":"8"}}
]}
```

The endpoint validates unique names, 2–5 scenarios, and the existing bounded goal model. Each scenario uses end-of-month contributions and a constant nominal annual return divided by 12. No market data, broker account, user information, or external API is needed. Calculations are stateless.

**Important:** Return assumptions are not forecasts or scenario probabilities. No inflation, fees, taxes or volatility are included. Results are not investment recommendations and are not persisted.
