# Tracking Architecture Decision Note

## Decision Summary
Adopt a contract-first, four-layer tracking architecture while preserving this repository as the tracker runtime baseline:
1. Tracker ingestion API
2. Persistence/query layer
3. Realtime delivery layer
4. Frontend map experience

This repository currently provides the embedded tracker-side foundation (A9G + MicroPython). Server and frontend layers are defined by contract and implemented by sibling agents.

## Architectural Boundaries
- **Tracker runtime (this repo baseline):** acquire GPS point, attach identity/timestamp/signature, POST to ingest API.
- **Backend API:** validate/authenticate payloads, normalize coordinates/time, persist immutable point records.
- **Query API:** serve latest position per tracker and bounded historical windows.
- **Realtime API:** broadcast validated ingested points to subscribers (UI/consumers).
- **Frontend:** render OSM map, live markers, and history playback using backend query + realtime feeds.

## Data Flow
1. Tracker sends signed `position.update` payload via `POST /api/v1/tracking/ingest`.
2. Backend validates schema, auth, freshness, and coordinate ranges.
3. Backend writes point record and updates latest-position projection.
4. Backend publishes `position.updated` event to realtime channel.
5. Frontend reads initial state (`/latest`, `/history`) and applies realtime updates.

## Key ADR Choices
- **Transport for ingest:** HTTPS JSON POST (works with constrained MicroPython clients).
- **Realtime for frontend:** WebSocket primary; SSE optional fallback.
- **Storage model:** append-only position points + materialized/latest-by-tracker view.
- **Auth model:** per-tracker signed request using shared secret (HMAC) and timestamp window.
- **Time standard:** ISO8601 UTC timestamps in payloads; backend stores canonical UTC.

## Non-Goals in This Task
- No implementation of backend/frontend features in this branch.
- No mutation of workflow graph.
- No schema migration or deployment script changes.

## Module Ownership Map (Non-overlapping)
- **Agent 1 (this task, planner/contracts):**
  - `docs/tracking/architecture.md`
  - `docs/tracking/runtime-constraints.md`
  - `docs/tracking/api-contracts.md`
- **Agent 2 (backend persistence/query):**
  - `server/db/**`
  - `server/repositories/**`
  - `server/services/history/**`
- **Agent 3 (backend ingest + realtime):**
  - `server/api/tracker-ingest/**`
  - `server/realtime/**`
  - `server/auth/tracker-signature/**`
- **Agent 4 (frontend map experience):**
  - `web/src/features/tracking-map/**`
  - `web/src/lib/realtime/**`
  - `web/src/lib/api/tracking/**`
- **Agent 5 (tests/validation/integration):**
  - `tests/contracts/**`
  - `tests/integration/tracking/**`
  - `docs/tracking/validation-report.md`

If actual repo paths differ, downstream agents should preserve ownership by matching module responsibility (not file names) and avoid cross-editing another agent's assigned area.
