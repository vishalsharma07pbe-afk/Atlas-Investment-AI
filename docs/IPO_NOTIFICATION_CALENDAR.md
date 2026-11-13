# Upcoming IPO calendar in notifications

The notification bell now offers **IPO calendar (30 days)** next to All alerts. It derives a date-ordered view from the IPO_UPCOMING, IPO_SUBSCRIPTION and IPO_ALLOTMENT alerts that were already fetched when the bell was opened. It makes **no additional network request**. The date window starts on the current calendar date in **Asia/Kolkata**, includes today and the next 30 days, and ignores malformed or missing event dates.

Each event retains its source attribution, publication timestamp and stale-subscription warning. The calendar displays only events actually present in the permissioned local notification feed. An empty calendar means no matching event was supplied, **not** that no IPO is scheduled. This is not an exchange calendar or a verified offering timetable. For live coverage, a rights-cleared IPO data provider remains necessary.

Tests: `cd frontend/trading-dashboard && npm test && npm run build`.
