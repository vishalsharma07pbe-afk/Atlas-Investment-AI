# AMFI NAV snapshot import

Use POST `/api/v1/intelligence/mutual-funds/amfi-nav-import` with a locally obtained AMFI-style semicolon-separated NAV text and selected scheme codes. Example:
```json
{"scheme_codes":["12345"],"text":"12345;INF000000001;INF000000002;Example Direct Growth;123.4567;12-Nov-2026"}
```

This is a bounded, read-only parser. It does not automatically fetch or persist market data. It reports invalid, missing, duplicate and stale scheme entries; selected scheme codes must match exact source identifiers. It is not historical performance data. Only source-attributed history can support trailing return analysis. No fund ratings are inferred.

The upstream AMFI endpoint, redistribution rights, production provider availability and real-account correctness have not been validated. Automatic ingestion should only be enabled after those checks, with rate limiting, cache expiry and explicit data rights. Never substitute fund names for verified scheme identifiers.
