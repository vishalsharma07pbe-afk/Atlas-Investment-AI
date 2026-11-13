# Broker-neutral reporting roadmap and initial implementation

ATLAS must not depend on Upstox alone. A unified reporting contract now supports **Groww, Zerodha Kite, Upstox, Angel One, Dhan, FYERS, ICICI Direct, HDFC Securities, and other statement-import brokers**. This release does **not** connect to any of their accounts; support means the report can represent positions labeled with those broker codes.

## Initial API

`POST /api/v1/intelligence/reports/brokers/consolidated`

Input: `report_date`, optional `max_price_age_days` and up to 2,000 manually supplied `positions`. Each position includes `broker`, `account_label`, `asset_type` (EQUITY, ETF, MUTUAL_FUND), stable `instrument_id` (ISIN or scheme identifier), `display_name`, `quantity`, `average_cost`, optional `last_price` and mandatory `price_as_of` when priced, and `source_type`.

Output: account-level valuations, cross-broker consolidated instrument quantities and valuations, portfolio totals, and stale/missing-price warnings. Incomplete valuation prevents an overall market value/P&L claim; no partial figure is presented as a total. All inputs are local user-provided data and no brokerage credentials are requested.

## Planned provider adapters

Each provider should have separate capabilities: account holdings, order/transaction history, contract notes, mutual fund statements, corporate actions, market data, and tax reports. Mark each capability as `API_VERIFIED`, `STATEMENT_IMPORT`, `UNAVAILABLE` or `NOT_VERIFIED` after checking actual provider docs and terms. **Do not assume every broker exposes every feature or has public API access.**

## Planned financial reports

- Consolidated holdings and broker-account breakdown
- Realized/unrealized P&L with dated prices and proper lot accounting
- Capital gains by fiscal year and holding period; tax classification reviewed against current rules
- Dividends, fees, charges and cash flows
- Allocation by asset class, sector, broker and concentration
- Mutual fund SIP, NAV and scheme performance with appropriate data source and date
- Portfolio risk, drawdown and benchmarks, subject to data completeness

A robust future ingestion path requires stable account IDs, idempotent transaction IDs, source provenance, statement versioning, reconciliation to broker balances, timezone handling, duplicate detection, immutable lot history, privacy controls, and an explicit consented account connection. None of those are silently claimed by this first report API.

## Verification

`cd intelligence && python3 -m unittest discover -s tests -v`
