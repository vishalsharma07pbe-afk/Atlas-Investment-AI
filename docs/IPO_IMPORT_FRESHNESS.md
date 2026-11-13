# Local IPO import freshness

The existing read-only `/api/v1/intelligence/notifications/providers/import-history` endpoint now includes a `freshness` object. It separates the most recent successful **APPLY** from the most recent successful **DRY_RUN**. A dry run never counts as an applied import.

Statuses:
- `NO_SUCCESSFUL_IMPORT`: no valid successful apply timestamp in the retained audit.
- `RECENT_IMPORT`: latest successful apply is at most 24 hours old.
- `IMPORT_STALE`: latest successful apply is more than 24 hours old.

Invalid, timezone-naive and future timestamps do not count; failed attempts do not count. These values are derived from the latest 100 locally retained audit entries, so older events may no longer be visible. The dashboard shows the status and both timestamps when import history is opened.

**Important:** This metric tracks local import activity, **not** the publication timestamp or accuracy of IPO subscription data, nor proof of provider connection, authorization or ongoing availability. For source data age, inspect the separate notification source health view. No automatic provider requests are made.
