# Authorized HTTPS IPO notification provider

ATLAS can now **optionally fetch** an IPO/market notification snapshot from a **licensed HTTPS JSON provider** using an operator-supplied exact endpoint and bearer token. It does **not** include a default provider, NSE/BSE scraping, guessed API routes, or a built-in scheduler. No external feed is connected by installing this PR alone.

## Setup

Obtain an endpoint that is explicitly licensed for collection and local display/redistribution. The endpoint must respond with the same JSON snapshot schema described in `docs/IPO_NOTIFICATION_IMPORT.md`. It must use HTTPS on port 443, with a public hostname, and return `application/json`.

Create a local config file outside source control, e.g. `intelligence/provider.json`:

```json
{
  "name": "Licensed provider",
  "endpoint": "https://licensed.example.org/alerts",
  "token_env": "ATLAS_PROVIDER_IPO_TOKEN",
  "collection_authorized": true,
  "redistribution_authorized": true,
  "enabled": true
}
```

**This endpoint is illustrative, not a real service.** Set your actual rights-cleared endpoint and matching provider name. Never commit credentials.

```bash
export ATLAS_PROVIDER_IPO_TOKEN="your-provider-issued-token"
cd intelligence
python3 -m app.authorized_ipo_provider --config provider.json
python3 -m app.authorized_ipo_provider --config provider.json --apply
```

The first command fetches and validates data but **does not write**. The second atomically updates `../data/notifications/alerts.json`, which the Docker intelligence service reads. Each run performs a single explicit HTTPS request. To update regularly, configure a local operator-managed scheduler **only after** confirming the provider's allowed polling frequency and licensing terms.

## Safety and provenance

- Explicit enablement and declared collection/redistribution rights are required.
- Bearer token is read from a named environment variable, not the JSON config; it is never printed.
- HTTPS certificate validation, a 10-second timeout, no HTTP redirects, JSON content type, a 1 MB response cap, and exact publisher name/URL matching are enforced.
- Provider payloads still pass per-alert timestamps, IPO subscription ratio, duplicate ID and atomic import validation.
- Local/non-public DNS results are rejected at preflight, but **DNS rebinding protection requires outbound firewall/egress restrictions in deployment**. Do not expose this operator tool as an arbitrary URL-fetching web API.
- Rights and content authenticity are operator-declared; this adapter does not independently certify the provider or exchange numbers.
- `live_feed_connected` in the CLI output means a provider request completed in that invocation. The existing notification and source-health APIs remain local-only and must not be interpreted as an active streaming connection.

Tests: `cd intelligence && python3 -m unittest discover -s tests -v`.
