# Known Limitations and Follow-Ups

## Current Limitations
1. Contract mismatch with orchestration target architecture:
- Current tracker payload is `{latitude, longitude}` only.
- Missing `trackerId`, `timestamp`, `speed`, `heading`, and `accuracy` fields.
- No request signing/auth verification despite `auth` setting presence.

2. Backend/frontend integration not present in this branch:
- No ingestion API implementation in-repo.
- No persistence/query endpoints for latest position or history.
- No realtime WebSocket/SSE service.
- No Leaflet/OpenStreetMap frontend playback client.

3. Location source is mocked:
- `getLocation()` returns hard-coded coordinates.
- Real GPS read path is commented out.

4. Port handling inconsistency:
- `Network.new` stores `settings["server"]["port"]`.
- `track()` calls `connect()` without forwarding that port, defaulting to 443.

5. HTTP response parsing is fragile:
- `Network.post()` returns full socket response bytes/string; mode handlers assume parse-ready JSON in places.
- Limited validation and error handling around response envelope parsing.

6. Resilience/observability gaps:
- No structured logs, metrics, or heartbeat/health endpoint.
- Retry loops can run indefinitely without backoff strategy tuning.

## Recommended Follow-Up Improvements
1. Align tracker payload contract to planned architecture:
- Include `trackerId`, `timestamp`, `lat`, `lon`, optional `speed`/`heading`/`accuracy`.
- Add signature/HMAC headers and backend verification.

2. Implement end-to-end platform layers:
- Ingestion API + schema validation.
- Persistence and query endpoints for latest/history.
- Realtime stream (WebSocket or SSE).
- OSM/Leaflet frontend with live markers and history playback.

3. Replace mocked location with GPS fix acquisition and validity filtering.

4. Honor configured port consistently in tracking path and normalize TLS behavior.

5. Add automated tests:
- Unit tests for request/response shaping.
- Integration smoke test with a mock HTTP server.

6. Add deployment observability:
- Structured logs, error counters, and delivery success metrics.
