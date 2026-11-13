# Permissioned IPO alert feed registry and repeatable inbox sync

This adds a source-registry layer over the existing notification snapshot importer. It enables an operator to consolidate many separately obtained, rights-cleared IPO and market-event snapshots into the single local notification feed used by the dashboard bell.

**No exchange API, website, or broker feed is automatically connected.** ATLAS does not scrape NSE/BSE or claim access to real-time IPO subscription rates. An authorized data provider or the operator must place valid snapshot JSON files in a local inbox first. The sync can then be invoked repeatedly by an operator-controlled schedule; it does not run background polling itself.

Create `intelligence/feeds.json` (not committed with credentials):

```json
{
  "feeds": [
    {
      "source_name": "Authorized publisher",
      "source_url": "https://example.org/ipo",
      "collection_authorized": true,
      "redistribution_authorized": true,
      "enabled": true
    }
  ]
}
```

`example.org` is a placeholder, **not a connected IPO feed**. The registry must exactly match the `source_name` and `source_url` fields of each snapshot. A disabled or unlisted publisher is skipped. Missing permissions reject enabled feed configuration. All snapshots also pass the existing per-alert schema validation, duplicate detection, provenance checks and timestamp rules.

From the `intelligence` directory:

```bash
python3 -m app.notification_feed_sync --registry feeds.json --inbox ../my-authorized-ipo-inbox
python3 -m app.notification_feed_sync --registry feeds.json --inbox ../my-authorized-ipo-inbox --apply
```

The first command is a **dry run**. The second updates `../data/notifications/alerts.json` with atomic writes. Re-running is idempotent for identical publication timestamps. At most 100 inbox JSON files per run are considered; symlinked files are ignored. Existing notification limits remain 200 records and 1 MB.

**Operational caveat:** this is a local adapter, not an independently authenticated data pipeline. The authorization booleans are operator attestations. Confirm licensing and source authenticity before supplying data. Do not treat a recent subscription timestamp as a guaranteed live figure. Use the existing 24-hour stale warning and follow the linked original source for verification.

Tests: `cd intelligence && python3 -m unittest discover -s tests -v`.
