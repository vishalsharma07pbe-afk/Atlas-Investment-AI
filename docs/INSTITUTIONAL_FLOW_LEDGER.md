# Institutional flow evidence ledger

## Scope
ATLAS can now store user-supplied FII/FPI/DII/retail buying and selling amounts with their source, market scope and trade date in a persistent SQLite volume. This is **not a live feed**. It does not independently verify source documents or claim that reported numbers are accurate. No trades or predictions are generated.

## Local workflow
1. Pull the branch and run `docker compose up --build -d`.
2. Open the Data Hub/market-data workspace. Use **Persistent FII / DII evidence ledger**.
3. Paste a CSV with exact header `trade_date,market,participant,buy_crore_inr,sell_crore_inr,source_name`. Example: `2026-11-12,NSE,FII,100,120,Example source`.
4. Save. Records persist across container restarts. Reimporting identical records is idempotent. A conflicting date/market/participant is rejected with HTTP 409; the entire batch remains unchanged.
5. Review net ₹ crore, date, source and calendar-day freshness. Market scopes remain separate, preventing accidental combined/NSE/BSE double counting.

## API
- `POST /api/v1/intelligence/institutional-flows/ledger` body `{"records":[{"trade_date":"2026-11-12","market":"NSE","participant":"FII","buy_crore_inr":"100","sell_crore_inr":"120","source_name":"Example source"}]}`
- `GET /api/v1/intelligence/institutional-flows/ledger?limit=100`

All endpoints are intended for trusted loopback access only; ATLAS currently lacks user authentication. Do not expose ports publicly. All amounts are user supplied; verification values are descriptive, not attestations. Calendar-day freshness can mark holiday data old.

## Tests
`cd intelligence && python3 -m unittest discover -s tests -p 'test_flow_ledger.py'`.
Also run the full Python test suite, React build/tests and Compose config validation.

## Blockers
Automated FII/DII ingestion requires an authoritative licensed source, approved usage rights, data format contracts and monitored freshness. None is assumed or bypassed here.
