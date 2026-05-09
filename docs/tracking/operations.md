# Tracking Operations Guide

## Purpose
Operator runbook for bringing up tracker ingestion from device to server and confirming live position flow.

## Startup Procedure
1. Confirm hardware state:
- A9G board powered and SIM inserted.
- Antennas attached as required by board setup.

2. Confirm settings file exists:
- Path: `/t/System/Settings.json`
- Required fields: `provider`, `server.host`, `server.port`, `server.routes.location`, `modes.currentMode`

3. Set runtime mode:
- `tracking` to send location payloads.
- `update` for update-instruction flow.
- `idle` for safe non-sending mode.

4. Start runtime by executing `main.py` on the board.

## Live Tracking Verification
In `tracking` mode, verify the following sequence:
1. Device log includes `Starting Tracking`.
2. Device connects and logs provider connection success.
3. Device repeatedly sends POST requests to `server.routes.location`.
4. Backend endpoint receives JSON payload with `latitude` and `longitude`.

Expected request body shape:

```json
{
  "latitude": 64.46382,
  "longitude": -44.5345
}
```

## Update Mode Verification
In `update` mode, verify:
1. Device requests `server.routes.update`.
2. Server returns JSON instruction envelope.
3. Device processes `action` and continues chunk/update loop.

## Failure Handling
- Network registration failures:
  - Runtime retries `network.start()` in a loop with 60-second delay.
  - If connectivity remains unstable, power-cycle board and validate SIM/provider state.
- Socket errors (`-256`):
  - Runtime attempts reconnect/retry in `Network.post()`.
- Malformed server response:
  - `ujson.loads()` can fail in update flow; inspect server response format and ensure valid JSON.

## Operational Assumptions
- Current `getLocation()` returns a static mock coordinate; GPS capture integration is still pending.
- Runtime currently handles one mode per run and does not include remote mode orchestration.
- Logs are console-only; no persistent telemetry pipeline exists in-repo.
