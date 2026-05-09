# Tracking Deployment Notes

## Scope
This repository currently contains device-side tracker runtime code for an A9G board (`main.py`, `Network.py`) using MicroPython modules (`cellular`, `gps`, `ujson`, `machine`, etc.).

The branch does **not** include a backend ingestion service, persistence/query API, realtime WebSocket/SSE service, or Leaflet/OpenStreetMap frontend. Deployment guidance in this document is therefore limited to tracker runtime deployment and its server contract assumptions.

## Runtime and Compatibility Prerequisites
- Hardware:
  - Ai-Thinker A9G-compatible board.
  - Active IoT SIM card (README references Hologram SIM usage).
- Runtime:
  - MicroPython/gprs_a9-compatible firmware with modules imported by `main.py` and `Network.py`.
  - Writable board filesystem at `/t/` (code expects `/t/System/Settings.json`).
- Network:
  - GPRS service available for the configured provider.
  - Reachable HTTP(S) endpoint for tracker POST requests.

## Required Configuration (Settings File)
The runtime is configured through `/t/System/Settings.json` (no environment variables are used in current code).

Minimum required keys inferred from code:

```json
{
  "provider": "<carrier-name>",
  "server": {
    "host": "example.com",
    "port": 443,
    "auth": "<token-or-placeholder>",
    "routes": {
      "location": "/tracking/location",
      "update": "/tracking/update"
    }
  },
  "modes": {
    "currentMode": "tracking",
    "tracking": {
      "interval": 30
    }
  }
}
```

Notes:
- `server.auth` is loaded by `Network.new` but not currently attached to outbound headers.
- `server.port` is loaded but `track()` currently calls `connect()` without forwarding configured port (see known limitations).

## Server Contract Assumptions
Current runtime contract from tracker to backend:
- Tracking mode: repeated `POST` to `routes.location` with JSON object shaped like:
  - `{"latitude": <number>, "longitude": <number>}`
- Update mode: `POST` to `routes.update` exchanging instruction payloads that include:
  - `action` (`update`, `print`, etc.)
  - `data` object for chunk/update state

No signature field, timestamp field, tracker ID, or history query contract is implemented in this branch.

## Rollout Checklist
1. Flash/install compatible MicroPython firmware on A9G board.
2. Copy runtime files to device filesystem:
   - `main.py`
   - `Network.py`
3. Create `/t/System/Settings.json` using the schema above.
4. Verify SIM insertion and provider registration (`networkCheck()` output on boot).
5. Set `modes.currentMode` to `tracking` for location sending or `update` for OTA-style flow.
6. Start runtime (`main.py`) and verify server receives POST requests.

## Deployment Validation
Use these signals as pass/fail criteria:
- Device prints `Connected to <provider>`.
- Device logs `Posted Location` in tracking mode.
- Server responds with valid HTTP response payload.
- Device exits cleanly and calls `shutdown()` without persistent socket failures.

## Rollback
If rollout fails:
1. Set `modes.currentMode` to `idle` to stop sending updates.
2. Revert to last known-good `main.py`/`Network.py` on device storage.
3. Restart device and re-check network registration before re-enabling `tracking` mode.
