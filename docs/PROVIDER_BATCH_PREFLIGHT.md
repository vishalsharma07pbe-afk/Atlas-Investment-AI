# Provider batch preflight (read-only)

The provider batch preflight is a **dry-run contract validation** for a prospective daily OHLCV provider adapter. It never calls Upstox, stores records, places orders, or enables automatic collection.

API: `POST /api/v1/intelligence/providers/batch-preflight`. Body: `provider` (UPSTOX), `source_reference`, `rights_confirmed`, `entitlement_confirmed`, `instrument_mapping_confirmed`, and `candles` (instrument_key, trade_date, open, high, low, close, volume). Supply 1–2,000 rows.

Validations include positive finite OHLC, consistent high/low bounds, nonnegative volume, no duplicate instrument/date pairs, no future dates, and conservative 3-calendar-day source freshness. Weekends and exchange holidays require an official calendar before production readiness can be evaluated.

The response **always blocks ingestion**, even with otherwise valid test fixtures, until a verified adapter, official instrument registry mapping, entitlement and license approval, production backend ingestion, and an exchange-aware freshness gate are implemented. This is not a live-feed connection.

Dashboard: Provider batch preflight in the market data health section. Use only test or authorized data, never credentials.
