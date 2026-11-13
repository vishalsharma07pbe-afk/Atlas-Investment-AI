# ATLAS Mutual Fund NAV Catalog (local-first)

## Delivered
The Mutual Funds workspace now includes a searchable scheme/NAV catalog backed by a durable SQLite volume in the intelligence service. Import an official AMFI NAV text report manually; the importer validates scheme codes, names, positive finite NAVs and non-future dates, ignores invalid rows, refuses duplicate scheme codes in one file, and never overwrites a newer NAV with an older date. Import and search APIs return source provenance and never claim a live connection.

## Source and licensing
AMFI publishes [NAV downloads](https://www.amfiindia.com/net-asset-value/nav-download) and daily end-of-day NAVs. Public availability does **not** itself prove permission for unattended automated harvesting, redistribution or commercial use. Until the applicable terms and entitlements are verified, ATLAS **does not fetch or refresh AMFI automatically**. Download the text report manually and upload it from the local UI. NAV is not an intraday stock quote.

## Local steps
1. Pull this branch, run `docker compose up --build -d`.
2. Open http://localhost:5173 and select **Mutual Funds**.
3. Download the text NAV report from the official AMFI site and import the .txt file using the NAV explorer.
4. Search by scheme name or code. The UI displays each NAV's source date and marks records older than five calendar days as older NAVs. Weekends and holidays can make otherwise valid NAVs appear old; no price is synthesized.
5. Stop/restart containers and verify records persist.

## API
- `GET /api/v1/intelligence/mutual-funds/status`
- `GET /api/v1/intelligence/mutual-funds/search?q=example&limit=30`
- `POST /api/v1/intelligence/mutual-funds/import` with UTF-8 AMFI semicolon-delimited text body, maximum 8 MB.

Frontend uses existing `/intelligence` Vite proxy. The intelligence API is only suitable for local trusted access because ATLAS has **no user authentication yet**. Never expose these ports publicly. The importer does not fetch external URLs or execute trades.

## Verification
Run `cd intelligence && python3 -m unittest discover -s tests -p 'test_nav_catalog.py'`. Run the existing Python CI suite and React build/tests. Test an invalid report, an older snapshot, a valid NAV report, and container restart. CI must pass before merging.

## Remaining blockers
- Confirm AMFI source usage rights before implementing automatic refresh.
- Obtain an authorized NSE/BSE stock quote provider; Upstox account verification is pending.
- Fund star ratings, factsheets, holdings, risk-adjusted returns and company financials require separate verified sources; none are fabricated.
