# Runtime, Deployment, and Compatibility Constraints

## Source Audit Scope
- Repository files inspected: `README.md`, `main.py`, `Network.py`.
- No backend web service, database schema, frontend app, Dockerfile, or CI pipeline exists in this repository at the time of writing.

## Current Runtime Baseline (Must Preserve)
- Device/runtime target is **A9G board running MicroPython** (per README and imports).
- Code depends on MicroPython modules and A9G-specific APIs:
  - `cellular`, `gps`, `machine`, `urequests`, `ujson`, `uos`, `uio`, `upip`, `ssl`, `socket`.
- Local file-system assumptions:
  - Base path is `"/t/"` and settings path is `"/t/System/Settings.json"`.
- Network transport behavior in `Network.py`:
  - Raw socket HTTP/1.1 construction and write/read loop.
  - Optional TLS wrapping when port is `443`.
  - Practical outbound payload/read buffer constraints (comment indicates ~130-byte safe buffer in some flows).

## Deployment Constraints
- This repository currently represents **tracker firmware/client-side behavior**, not the server.
- Server-side APIs specified in `docs/tracking/api-contracts.md` are external dependencies and should be implemented in sibling/backend work, not in this firmware baseline task.
- Connectivity assumptions:
  - GSM/GPRS link may fail intermittently; retry/reset behavior already exists and must remain compatible.
  - Tracker can send repeated HTTP POST requests with low throughput and unstable latency.

## Compatibility Constraints for New Tracking Work
- Preserve MicroPython compatibility in existing files:
  - Do not introduce CPython-only libraries into tracker runtime files.
  - Keep memory usage bounded; avoid large in-memory payload accumulation.
- Keep HTTP contracts simple JSON over HTTPS with small request bodies.
- Ensure auth mechanism can be represented as static headers/tokens on constrained clients.
- Do not assume persistent WebSocket capability on tracker firmware; realtime is primarily server-to-frontend.

## Coding Conventions Observed
- Python style is pragmatic and runtime-oriented, with low-level networking and explicit retries.
- JSON serialization/deserialization via `ujson`.
- Functions are currently synchronous/blocking.
- Error handling often logs and retries/reset device.

## Implications for Other Agents
- Backend agent should optimize ingest endpoint for constrained clients:
  - tolerant of jitter/retries,
  - idempotency safeguards for duplicate points,
  - compact JSON contract.
- Frontend agent should consume realtime from backend; tracker firmware does not directly drive frontend.
- Testing agent should separate:
  - device/runtime smoke checks (MicroPython compatibility),
  - backend API contract tests (standard server runtime).
