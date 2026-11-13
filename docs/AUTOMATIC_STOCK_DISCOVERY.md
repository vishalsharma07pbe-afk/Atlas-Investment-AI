# Automatic stock discovery and Upstox mapping

The Stock Explorer now searches the existing local instrument registry as the user types (debounced 350 ms), with race protection and explicit errors. Clicking a result continues to the existing technical research view.

A separate provider resolution endpoint resolves verified active NSE equity instruments with valid Indian ISINs to the documented `NSE_EQ|<ISIN>` key format. BSE and missing/invalid identifiers remain blocked until a provider-sourced instrument master can be validated. Resolution **does not subscribe to a live feed** and does not imply a current price.

The registry is currently populated by lawfully sourced imports. Automatic discovery of *new* instruments requires a separate authorized provider instrument-master sync. Mutual fund scheme identifiers, daily NAV, ratings, expenses, and factsheets require separate data pipelines; do not confuse NAV with intraday prices.

API: `GET /api/v1/intelligence/providers/upstox/resolve?instrument_id=<local id>`. Response includes readiness and an explicit blocker; it never contains a token or a quote.
