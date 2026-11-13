# Mutual fund NAV refresh preflight

POST `/api/v1/intelligence/mutual-funds/nav-refresh-preflight` with `source_name`, `source_authorized` (explicit caller attestation), `expected_scheme_codes`, and `records` containing exact numeric `scheme_code`, positive finite `nav`, and ISO `as_of`.

The endpoint checks missing, unexpected and duplicate scheme codes, future/stale (>7 days) dates, mixed valuation dates and source authorization attestation. Any blocker returns `BLOCKED`. An otherwise valid batch returns `READY_FOR_MANUAL_REVIEW`, **not** provider verification or ingestion authorization.

This endpoint performs **no external fetching, writes, scheduled refresh, trading, or portfolio mutation**. The attestation is supplied by the caller and is not independently verified. A production provider connector requires separately verified provider terms, credentials, transport and operational controls.
