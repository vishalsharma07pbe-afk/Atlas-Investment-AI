# Mutual fund NAV refresh preflight

POST `/api/v1/intelligence/mutual-funds/nav-refresh-preflight` with `source_name`, `source_authorized` (explicit caller attestation), `expected_scheme_codes`, and `records` containing exact numeric `scheme_code`, positive finite `nav`, and ISO `as_of`.

The endpoint checks missing, unexpected and duplicate scheme codes, future/stale (>7 days) dates, mixed valuation dates and source authorization attestation. Any blocker returns `BLOCKED`. An otherwise valid batch returns `READY_FOR_MANUAL_REVIEW`, **not** provider verification or ingestion authorization.

This endpoint performs **no external fetching, writes, scheduled refresh, trading, or portfolio mutation**. The attestation is supplied by the caller and is not independently verified. A production provider connector requires separately verified provider terms, credentials, transport and operational controls.

## Dashboard workflow

In the Mutual Funds workspace, open **Validate a NAV batch**. Enter the source name, expected numeric scheme codes, and a JSON array of NAV records (scheme_code, nav, as_of). Confirm that you are authorized to use the supplied records, then select **Validate batch**. The panel shows BLOCKED or READY_FOR_MANUAL_REVIEW with missing/unexpected/duplicate schemes, stale/future NAVs and matched valuation dates. A ready result is only a manual-review signal; it never saves or updates a portfolio.

## Export validation report

After validation, choose **Export validation report (JSON)** to download a browser-generated diagnostic record. The report contains the UTC validation timestamp, result status, blocker codes, scheme coverage diagnostics, source name and user attestation. It intentionally excludes raw NAV prices, position units and holdings. Scheme codes and source name are still included, so review the file before sharing. This is a client-side download only: ATLAS does not persist the report or raw NAV batch on the server.
