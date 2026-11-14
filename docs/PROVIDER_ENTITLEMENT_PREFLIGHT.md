# Provider entitlement preflight (read-only)

This module is a **review aid**, not a credential manager, provider connector or independent verification system. It cannot grant data access. A manually supplied permission declaration never authorizes unattended ingestion. The API always reports automatic collection disabled, including for apparently valid declarations.

## Workflow
1. Confirm the provider's current contract/terms with the rights holder, including exact dataset, mode (manual import, automated fetch or streaming), permitted purpose, redistribution limits, geographic scope, quotas, and expiration.
2. For local record-keeping, create `data/entitlements/sources.json` from the example below. Do not store API keys, secrets, contracts or personal data in this file. It is read-only mounted inside the intelligence container and should not be committed.
3. Run `docker compose up --build -d`, open the **Market & Data Health** workspace and review **Provider entitlement preflight**. Select a dataset and mode to see the specific blockers.
4. To activate a provider in the future, separately implement independent entitlement verification, authenticated connection checks, rate limits, freshness SLAs, reconnection behavior and licensed endpoint-specific integration tests. None of those checks is bypassed by this manifest.

Example (replace timestamps and reference with locally reviewed non-secret identifiers):
```json
{
  "version": 1,
  "sources": [{
    "source_id": "EXAMPLE_VENDOR",
    "dataset": "EQUITY_QUOTES",
    "mode": "STREAM",
    "purpose": "PERSONAL_RESEARCH",
    "permission_reference": "internal-review-reference-only",
    "reviewed_at": "2026-11-13T00:00:00+00:00",
    "valid_until": "2026-12-13T00:00:00+00:00"
  }]
}
```

Supported datasets: `EQUITY_QUOTES`, `EQUITY_DAILY`, `MF_NAV`, `INSTITUTIONAL_FLOWS`, `GLOBAL_NEWS`. Supported modes: `MANUAL_IMPORT`, `AUTOMATED_FETCH`, `STREAM`. Supported purposes: `PERSONAL_RESEARCH`, `REDISTRIBUTION`.

## API
- `GET /api/v1/intelligence/entitlements`: redacted local declarations, expiry status, and review-only status.
- `GET /api/v1/intelligence/entitlements/preflight?dataset=EQUITY_QUOTES&mode=STREAM&purpose=PERSONAL_RESEARCH`: scope-specific blockers. Invalid scopes return HTTP 400.

Missing, malformed, oversized, expired or mismatched declarations fail closed. Timestamps must include timezone offsets. Confidential permission references are never returned. The manifest is capped at 64 KB and 100 entries.

## Verification
`cd intelligence && python3 -m unittest discover -s tests -p 'test_entitlement_registry.py'`
Run full Python, React, Compose and Spring Boot CI before merging.

## Remaining external blockers
Upstox account activation/approval and an independently verified provider entitlement are not available. AMFI and global news unattended collection rights remain unverified. No live feed or trade execution is activated.
