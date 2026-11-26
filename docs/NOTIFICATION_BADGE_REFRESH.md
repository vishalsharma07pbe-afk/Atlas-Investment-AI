# Notification badge refresh

The global notification bell now checks the **lightweight local summary endpoint** when the dashboard mounts, when the browser window regains focus, when the tab becomes visible, and at most once every five minutes while visible. Hidden tabs skip scheduled refreshes. Pending fetches are aborted on component unmount and overlapping summary requests are suppressed.

Only alert IDs and revision keys are fetched by these checks. Full IPO details, subscription ratios, and other notifications **remain click-to-load**. New revisions of previously read alerts become unread again, and the bell count updates when the user returns to the dashboard. The summary error indicator clears after a successful retry.

The summary reads only local imported alerts; this is **not a live IPO feed or a background exchange scraper**. It does not generate system-level push notifications, nor does it fetch notification details without user action.

Test with `cd frontend/trading-dashboard && npm test && npm run build`.


## Open-panel delivery integration
After the user opens the panel, public details and owner-local inbox reuse foreground-only single-flight polling at 60 seconds, with visibility-triggered refresh and abort on close. Closed panels retain metadata-only checks. An older badge response cannot replace a newer detail snapshot; late closed-panel responses cannot mark alerts read. Successful server read acknowledgements survive an older inbox poll. Failed detail refreshes are shown as unavailable, not as an empty/current feed. No provider calls, external push, or new backend endpoints. Actual browser/device verification remains required.
