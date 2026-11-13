# Upstox V3 WebSocket transport (read-only)

This module adds a **server-side transport**, not a complete live-price feature.

- Authorizes each session through the existing Upstox V3 HTTPS feed authorization client.
- Connects to the returned signed WebSocket endpoint.
- Subscribes using V3 `ltpc` instrument keys.
- Handles binary frames only, enforcing frame size bounds.
- Reauthorizes on reconnect, with capped exponential backoff and bounded retries.
- Does not expose bearer tokens, signed URLs, frames or order execution to browser APIs.

The transport requires `websockets` and a **trusted binary Protobuf decoder callback**. It is not started automatically: enabling a raw transport without validated decoding, data rights and authenticated credentials would misrepresent live-price readiness. No quote is displayed until decoded, validated, timestamped, and published through an authorized backend data service.

Next: compile the official V3 Protobuf schema, implement safe decoding and instrument-key matching, validate trade timestamps and market sessions, persist/cache quotes, add subscription lifecycle and dashboard streaming. Local user OAuth and actual provider account authorization remain prerequisites.

Run tests with `cd intelligence && python -m unittest discover -s tests`.
