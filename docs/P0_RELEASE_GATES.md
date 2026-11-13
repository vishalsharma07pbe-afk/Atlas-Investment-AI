# P0 readiness: local configuration safety gate

Run `python scripts/check_p0_local_config.py --env-file .env` before starting a local instance. The command exits nonzero if the password is missing/placeholder, an unknown provider is selected, or automated/provider data is requested without locally declared rights, entitlement, and a token. It does not print credential values.

The gate checks **declarations only**. It does not verify legal entitlements, actual provider API access, exchange coverage, token validity, live quote freshness, authentication, or production readiness. It does not start any market feed or make a provider request. Keep all Docker services loopback-bound and do not expose ATLAS publicly without real authentication and user isolation.

## P0 acceptance gates

1. **Market data:** authenticated, entitled Upstox access; official instrument mapping; accurate search and quote/candle provenance; verified fresh data with failure states.
2. **Mutual funds:** permitted source and refresh mechanism; scheme identifier mapping; daily NAV history and provenance; no fabricated ratings.
3. **Reliability:** scheduler, retries/backoff, idempotency, stale-source alarms, audit records and recovery tests.
4. **Security:** real authentication, per-user authorization and isolation, secret storage, rate limits, and security testing. The local gate is not a substitute.
5. **Stability:** all CI jobs green; integration/e2e tests; restore drills; release checks and observability.

No P0 item is considered complete until its acceptance checks are independently verified. The existing system remains local-only and manual-data-first until then.
