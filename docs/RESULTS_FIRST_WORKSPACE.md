# Results-first workspace

The existing frontend now separates Overview, My Portfolio, Mutual Funds, four opportunity horizons, Market Intelligence, Stock Explorer, AI Research and Settings. Previously saved route IDs 0–8 remain valid; portfolio and market intelligence use 9 and 10. No backend API, data provider, holding storage or theme preference is replaced.

Overview starts with recorded portfolio metrics, automatic attention items and cached market/fund observations. Portfolio management and optional manual tools have their own page. Settings prioritizes the existing connection and readiness views, with diagnostic and ingestion utilities in expandable sections. Market Intelligence retains the original company, institutional, news, source-audit and outcome tools. Advanced sections do not mount until first opened and retain their state while collapsed on that page. Navigation has a compact menu on smaller screens, and the existing theme and appearance controls remain unchanged.

A stale hard-coded MANUAL provider label and unreachable offline placeholder were removed. Disabled automatic research cannot display saved picks as current. Periodic portfolio reads survive React StrictMode effect replay. The new UI does not imply missing data or AI research is complete.

Validation: navigation and disclosure regression tests, existing React suite and CI. Actual browser viewport/visual acceptance on the local installation remains required. No claim of a complete recommendation engine or verified live-data deployment.
