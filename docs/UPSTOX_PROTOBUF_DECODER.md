# Upstox V3 binary feed decoding

Implements a bounded, narrow Protobuf wire decoder for `FeedResponse` from the official Upstox `MarketDataFeedV3.proto`. Supported fields: response `type=1` (live_feed), `feeds` map, `Feed.ltpc`, `Feed.fullFeed.marketFF/indexFF.ltpc`, and `Feed.firstLevelWithGreeks.ltpc`. Market-info and initial snapshot messages do **not** become live quotes. Frames must be binary, bounded, and match a subscribed instrument key. Invalid or stale trade timestamps are rejected using the existing freshness policy.

Schema reference: https://github.com/upstox/upstox-python/blob/master/examples/websocket/market_data/v3/MarketDataFeedV3.proto

This is an intentionally limited decoder, not the entire Upstox schema. A transport consumer must still establish actual provider authorization, verify market session state, connect the decoder to the transport, persist/cache quotes, and publish safely to the UI. It does not start the feed or claim live data availability.

Run `cd intelligence && python -m unittest discover -s tests`.
