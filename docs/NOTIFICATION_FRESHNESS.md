# IPO notification freshness and revisions

The notification bell now treats an alert's stable ID plus publication timestamp as its unread revision key. When a rights-cleared snapshot importer updates the publication timestamp for the same IPO subscription alert, the updated version becomes unread again. The lightweight summary returns only IDs and revision keys, not alert descriptions or subscription rates. Full details still load only after clicking the bell.

The panel filters IPO announcements, subscription rates, allotments, market events, corporate actions, research updates and risk warnings without additional requests. Subscription rates whose as-of timestamp is over 24 hours old display **STALE SNAPSHOT — do not treat as live**. This is a conservative age-based warning, not a guarantee that younger data is current or authentic.

No live exchange feed is connected; operator-supplied data remains unverified. The original alert IDs field remains for compatibility with existing clients. Unread state is browser-local and does not synchronize across devices.
