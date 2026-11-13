# Portfolio Concentration & Risk Limits

This module checks a locally recorded portfolio against configurable user-defined exposure limits. It includes a read-only Python engine, POST API, React UI, tests and documentation.

## Usage

Open **My Portfolio → Portfolio concentration & limits**. Set maximum single holding weight, equity exposure, mutual fund exposure and combined top-three holdings weight. Click **Check concentration** to see recorded holding weights, breaches and any unpriced holdings.

API: `POST /api/v1/intelligence/portfolio/concentration`

Example:
```json
{"max_single_holding_percent":"25","max_equity_percent":"80","max_mutual_fund_percent":"80","max_top_three_percent":"60"}
```

Values are calculated as recorded quantity multiplied by the **manually recorded last price**, not live prices. Holdings without a recorded price are excluded from the denominator and explicitly listed; the status is `PARTIAL_PRICE_COVERAGE` in that case. If no positive recorded value exists, the status is `NO_PRICED_VALUE` and no exposure conclusions are drawn. Limits are user-defined preferences, not recommended thresholds.

**Limitations:** This is a concentration check, not a portfolio volatility or loss forecast. It does not look through mutual funds to their underlying holdings, measure cross-holding correlations, assess sector concentration, guarantee diversification, access broker accounts, or place trades. Prices may be stale. No trades or rebalancing are suggested.
