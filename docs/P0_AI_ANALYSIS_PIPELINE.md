# P0 AI analysis pipeline — internal research-only preview

New endpoints in the intelligence service and Spring Boot proxy:
- `GET /api/v1/ai/providers/health` — enabled flags and local RPM/RPD ledger usage; does not claim remote connection health.
- `POST /api/v1/ai/analyze/{symbol}` — exact symbol match, strict allowlisted JSON body, parallel enabled-model verdicts and disagreement summary.

Example JSON body: `{"symbol":"RELIANCE","market":"NSE","price_change_pct":1.2,"technical_summary":"RSI 14: 55"}`.

**Security:** Spring Boot proxy is disabled by default (`ATLAS_AI_PROXY_ENABLED` / Spring `atlas.ai.proxy-enabled` property). Do not enable on a public network: there is no authenticated user identity or per-user authorization yet. Intelligence service must also remain private. The pipeline does **not** automatically retrieve portfolio holdings, upstream technicals, news, or real-time prices. Those need authenticated and independently verified upstream wiring; user-supplied indicators are not verified market evidence.

The response exposes each model's JSON verdict and majority agreement/conflict, not an actionable recommendation. `confidence_pct` is an uncalibrated model self-rating, not a calibrated likelihood. Quota reservation occurs before model invocation; paid providers require their existing opt-ins.
