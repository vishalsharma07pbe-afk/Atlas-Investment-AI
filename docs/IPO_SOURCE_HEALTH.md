# IPO notification source health

ATLAS now provides an explicit **Check source health** control inside the notification bell. This loads diagnostic metadata only when clicked, separately from the alert detail request.

Configure an operator-managed `data/notifications/feeds.json` file using the permission-gated registry schema documented in `docs/IPO_FEED_REGISTRY.md`. The existing Compose read-only mount makes the file available to the intelligence service. The repository does not ship a connected source registry or live feed.

`GET /api/v1/intelligence/notifications/sources/health` returns each configured source's enabled flag, permission declaration, count of matching locally imported alerts, latest publication time, most recent subscription snapshot time, and source status:

- `DISABLED`: registry source disabled
- `PERMISSION_NOT_DECLARED`: permission flag missing
- `NO_ALERTS_IMPORTED`: enabled source has no matching alerts
- `SUBSCRIPTION_STALE`: newest subscription snapshot is over 24 hours old
- `LOCAL_DATA_AVAILABLE`: matching locally imported alerts exist; this does **not** mean live connectivity
- `NOT_CONFIGURED`: no source registry file exists

The API does not fetch external data, validate legal permissions, authenticate publisher reports or guarantee current IPO rates. It reads bounded local metadata and never displays fabricated source connectivity. Invalid local data fails closed.

Tests: `cd intelligence && python3 -m unittest discover -s tests -v` and `cd frontend/trading-dashboard && npm test && npm run build`.
