# Autonomous portfolio valuation

The backend now owns periodic valuation refresh. The existing authenticated manual refresh endpoint delegates to the same owner-scoped service, preserving its response shape. Browser polling reads saved valuations rather than requesting provider quotes each minute.

Compose enables the scheduler by default. Set ATLAS_PORTFOLIO_AUTO_REFRESH_ENABLED=false to disable it. Each pass claims at most five due holdings, using a persisted last-attempt timestamp and a 15-minute minimum interval per holding. Expired or absent Upstox vault credentials are excluded from background equity requests. Mutual fund values use the existing AMFI-backed NAV store. History backfill uses the authorized existing daily adapter for holdings with insufficient or old data, excluding today's possibly incomplete candle. No automatic holdings deletion, broker sync, order placement, or paid AI use is introduced.

V18 adds one nullable timestamp and index only. Existing holdings and user isolation are unchanged. The single local backend is the intended deployment; no claim of full distributed scheduling or real-time quote freshness. The current provider quote timestamp semantics still require provider-specific verification. Initial/on-demand refresh remains available, including after reconnecting a broker.

Verification: with an authorized vault token, add a holding, close the browser, wait for the background pass, then reopen and check recorded prices and history. Confirm absent/expired credentials do not trigger background equity requests, NAV does not regress to an older date, failures do not prevent other holdings from being attempted, and a second user's holdings remain isolated. CI tests do not replace this authorized live check.
