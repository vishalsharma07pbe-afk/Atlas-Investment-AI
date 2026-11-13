# Notification badge refresh

The global notification bell now checks the **lightweight local summary endpoint** when the dashboard mounts, when the browser window regains focus, when the tab becomes visible, and at most once every five minutes while visible. Hidden tabs skip scheduled refreshes. Pending fetches are aborted on component unmount and overlapping summary requests are suppressed.

Only alert IDs and revision keys are fetched by these checks. Full IPO details, subscription ratios, and other notifications **remain click-to-load**. New revisions of previously read alerts become unread again, and the bell count updates when the user returns to the dashboard. The summary error indicator clears after a successful retry.

The summary reads only local imported alerts; this is **not a live IPO feed or a background exchange scraper**. It does not generate system-level push notifications, nor does it fetch notification details without user action.

Test with `cd frontend/trading-dashboard && npm test && npm run build`.
