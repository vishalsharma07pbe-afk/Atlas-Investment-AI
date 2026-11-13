# ATLAS Notification Center — click-to-load IPO and market alerts

The global header now has a bell icon with an unread-count badge. On initial dashboard load the browser requests only `GET /api/v1/intelligence/notifications/summary` (alert IDs and count). **Full alert details are requested only when the user clicks the bell**, via `GET /api/v1/intelligence/notifications`. The panel displays IPO upcoming, IPO subscription, IPO allotment, corporate actions, market events, research updates and risk warnings. Unread IDs are tracked in browser localStorage, per browser/device, and marked read after a successful panel load.

## Supplying alerts

The intelligence container reads the read-only host file `data/notifications/alerts.json`. The repository ships with `[]` intentionally: **no live IPO or subscription feed is connected**, and ATLAS must never invent upcoming IPOs or subscription rates. A separate authorized importer or operator may write validated attributed records to this file; the intelligence service itself does not scrape or update it.

Example **illustrative schema only, not a real IPO**:

```json
[
  {
    "id": "ipo-example-2026-11-13",
    "category": "IPO_SUBSCRIPTION",
    "title": "Illustrative IPO subscription update",
    "description": "Sample only, do not treat as live market data.",
    "event_date": "2026-11-20",
    "published_at": "2026-11-13T12:00:00+05:30",
    "source_name": "Illustrative source",
    "source_url": "https://example.org/ipo",
    "subscription_total_x": "2.35",
    "subscription_as_of": "2026-11-13T11:30:00+05:30"
  }
]
```

Each alert requires a stable unique ID, category, title, description, publication timestamp with timezone, source name and HTTPS URL. Subscription alerts additionally require a nonnegative total subscription multiple and its as-of timestamp. Source claims are operator-supplied and not independently authenticated; users must check official exchange and registrar disclosures. The reader is limited to 200 records and a 1 MB file, validates records and rejects duplicate IDs. Missing file means an empty feed, invalid files produce a 503 rather than misleading results.

## Limitations and future connections

This release implements the UI, badge, lazy loading, local source contract and tests. It does **not** fetch current IPO calendars, live subscription rates, broker recommendations or exchange notices. Future source adapters should use official/licensed sources, scheduled bounded ingestion only with permission, publication/retrieval provenance, timestamped subscription snapshots, and stale-data warnings. A badge count is a count of locally supplied unseen records, not an assurance of live market coverage.

Run `cd intelligence && python3 -m unittest discover -s tests -v`, `cd frontend/trading-dashboard && npm test && npm run build`, and `docker compose config`.
