# Permissioned IPO and market notification snapshot import

ATLAS now includes an **offline, operator-triggered** snapshot importer that can populate the notification bell introduced in PR #23. No background scraping or unverified live IPO feeds are implied.

Prepare a JSON snapshot from a source for which you have explicit collection and redistribution permission:

```json
{
  "source_name": "Authorized research publisher",
  "source_url": "https://example.org/ipo",
  "retrieved_at": "2026-11-13T12:30:00+05:30",
  "collection_authorized": true,
  "redistribution_authorized": true,
  "alerts": [
    {
      "id": "illustrative-ipo-2026-11-13",
      "category": "IPO_SUBSCRIPTION",
      "title": "Illustrative IPO subscription snapshot",
      "description": "Demonstration only, not actual market data.",
      "event_date": "2026-11-20",
      "published_at": "2026-11-13T12:00:00+05:30",
      "source_name": "Authorized research publisher",
      "source_url": "https://example.org/ipo",
      "subscription_total_x": "3.4",
      "subscription_as_of": "2026-11-13T11:55:00+05:30"
    }
  ]
}
```

The example above is **not real IPO information**. The importer validates source attribution, publication/retrieval times, subscription ratios and snapshot permissions; records are deduplicated by stable ID, newer publication timestamps replace older versions, and output writes are atomic. At most 200 alerts and 1 MB are retained. Importing does not authenticate a publisher, confirm the permissions claimed, or verify financial figures.

From the `intelligence` directory:

```bash
python3 -m app.notification_import ../my-authorized-snapshot.json
python3 -m app.notification_import ../my-authorized-snapshot.json --apply
```

The first command is a dry run. The second updates `data/notifications/alerts.json` relative to the current working directory, so **from `intelligence` use `--output ../data/notifications/alerts.json`**:

```bash
python3 -m app.notification_import ../my-authorized-snapshot.json --output ../data/notifications/alerts.json --apply
```

Docker Compose mounts that file read-only in the intelligence container. Refresh the dashboard to update the bell's lightweight count; opening the bell fetches full details on demand. This is not an automatic refresh service; use only rights-cleared, sourced snapshots. For a production data connection, implement an authorized exchange/registrar adapter with timestamps and source auditing.

Tests: `cd intelligence && python3 -m unittest discover -s tests -v`.
