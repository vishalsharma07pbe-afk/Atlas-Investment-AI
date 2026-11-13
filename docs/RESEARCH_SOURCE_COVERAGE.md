# Broker research source coverage audit

The endpoint `POST /api/v1/intelligence/research/brokers/coverage` accepts an instrument identifier, optional evaluation date, freshness window and user-submitted research records matching the existing broker research comparison schema.

It returns one coverage row for every supported provider label (Groww, Zerodha, Upstox, Angel One, ICICI Direct, HDFC Securities, Motilal Oswal, Sharekhan, Kotak Securities, Axis Securities, SBI Securities, Nuvama, JM Financial, Dhan, FYERS, and other sources). Rows distinguish `FRESH_USER_SUBMITTED`, `STALE_USER_SUBMITTED` and `NO_REPORTS_SUPPLIED`, including latest publication date and count. The count of supported labels is not the count of connected research feeds; all `connected_feed` fields are false until real provider-specific integration is verified.

Missing reports do not imply a broker has no research or recommends selling. User-submitted metadata is not independently authenticated. No background scraping, automatic retrieval, trading or financial advice is enabled.

Run `cd intelligence && python3 -m unittest discover -s tests -v`.
