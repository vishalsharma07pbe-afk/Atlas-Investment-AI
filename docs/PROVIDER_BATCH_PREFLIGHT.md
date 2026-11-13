# Provider batch preflight (read-only)

The provider batch preflight is a **dry-run contract validation** for a prospective daily OHLCV provider adapter. It never calls Upstox, stores records, places orders, or enables automatic collection.

API: `POST /api/v1/intelligence/providers/batch-preflight`. Body: `provider` (UPSTOX), `source_reference`, `rights_confirmed`, `entitlement_confirmed`, `instrument_mapping_confirmed`, and `candles` (instrument_key, trade_date, open, high, low, close, volume). Supply 1–2,000 rows.

Validations include positive finite OHLC, consistent high/low bounds, nonnegative volume, no duplicate instrument/date pairs, no future dates, and conservative 3-calendar-day source freshness. Weekends and exchange holidays require an official calendar before production readiness can be evaluated.

The response **always blocks ingestion**, even with otherwise valid test fixtures, until a verified adapter, official instrument registry mapping, entitlement and license approval, production backend ingestion, and an exchange-aware freshness gate are implemented. This is not a live-feed connection.

Dashboard: Provider batch preflight in the market data health section. Use only test or authorized data, never credentials.

## Browser-side credential guard

The dashboard rejects JSON containing credential-like field names (including nested or array entries) such as `access_token`, `refresh_token`, `api_key`, `api_secret`, `client_secret`, `authorization`, `bearer_token`, or `password` before making a network request. This is defense-in-depth for accidental token paste, not a replacement for backend redaction, access control, or secure credential storage. Do not paste secrets into the dashboard, including under arbitrary field names or in string values. The dry-run API remains blocked and does not authorize ingestion.

Regression tests cover nested credential rejection, zero network requests for blocked input, and the expected blocked dry-run response.
