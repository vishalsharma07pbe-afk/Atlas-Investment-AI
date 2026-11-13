# IPO Operations: local import history and source health

The notification center's **Check source health** panel now includes **Check provider import history**. Both are user-triggered and read-only. They show locally registered source status, imported-alert counts, stale subscription timestamps, and the most recent provider import attempts.

The new endpoint `GET /api/v1/intelligence/notifications/providers/import-history` reads `ATLAS_IPO_IMPORT_AUDIT` (default `/app/data/provider-import-audit.json`), already within the read-only Docker notifications mount. It returns at most 100 audit entries, newest first, with an explicit field allowlist; raw errors, tokens, provider URLs and payloads are never returned. Missing audit files yield an empty `NOT_CONFIGURED` result. Invalid files fail closed with HTTP 503.

To generate records, operators must explicitly run `python3 -m app.ipo_provider_audit --config provider.json --apply` in the intelligence directory (see [IPO_PROVIDER_IMPORT_AUDIT.md](IPO_PROVIDER_IMPORT_AUDIT.md)). The dashboard cannot start provider imports, modify credentials or trigger external requests. A successful audit record only proves a local import operation was recorded; it does not certify data accuracy, rights or continuous live connectivity.

Run Python tests and frontend build/tests before merging.
