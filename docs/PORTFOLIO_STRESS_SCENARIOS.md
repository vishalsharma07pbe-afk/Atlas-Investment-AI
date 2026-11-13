# Portfolio stress scenarios (research-only)

`GET /api/v1/intelligence/portfolio/stress-scenarios`

This read-only endpoint applies the same assumed percentage move to **each priced holding**. It is not a stock prediction or a portfolio Value-at-Risk model.

| Scenario | Uniform assumed move |
| --- | ---: |
| SEVERE_DOWNSIDE | -30% |
| BEAR | -15% |
| BASE_UNCHANGED | 0% |
| BULL | +15% |

The response reports the priced subset's recorded value, invested cost, stressed value, change and hypothetical unrealized P&L. Holdings with missing manually entered prices are listed separately and **excluded** from stress valuation. No external market data or AI service is called.

**Important limitations:** prices may be stale, shocks are illustrative and uniform, assets are not modeled for correlation, and the endpoint does not issue buy/sell actions. This endpoint uses the existing portfolio backend and therefore inherits the current alpha's local-only security limitation. Do not expose it publicly without authentication.
