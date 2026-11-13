# Freshness SLOs (internal targets, not provider guarantees)

| Data | Collection target | Stale handling |
|---|---|---|
| Licensed live quotes | event-driven; heartbeat 5s | suppress new signals if heartbeat >15s in continuous session; tune to feed contract |
| 1m candles | close + 10s target | quarantine if >30s late; incomplete candle never final |
| 5m/15m candles | close + 15s target | quarantine if >60s late |
| FII/DII | poll every 15m in expected publication window, then hourly | carry forward with original report date; never label old flow as today's |
| Bulk/block deals | poll every 5m during session; reconcile after publication | retain revisions |
| Short-sale disclosures | poll around release; daily reconciliation | disclosure is not intraday order flow |
| Company announcements | event stream or 1m poll where licensed | alert includes publication time |
| Global news | provider poll 1–2m | show age, source and confidence |
| Macro releases | refresh calendars hourly; check event time every minute | schedule is not the actual release |
| Shareholding reports | daily filing discovery | preserve reporting period; never call quarterly data live |

Store event_time, published_at, received_at, source_id, source_revision, license_scope,
verification_status and raw_payload_hash. Store UTC; render Indian sessions in Asia/Kolkata.
