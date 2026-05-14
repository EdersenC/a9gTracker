# Data Architecture Spec (Orchestration #6, Agent 3)

Status: needs_review  
SpecContainer: `data_architecture`  
Owner: Data Architecture Spec Agent

## Scope
Define durable data shapes and in-memory state for a 2-party network where one user's AI harness can perform work for another harness.

Accepted decisions applied:
- Persistence strategy: SQLite
- Runtime/UI target: CLI/text

## Inputs Consumed
- Product Spec (dependency): product boundaries, non-goals, acceptance criteria
- System Architecture Spec (dependency): module boundaries, integration contracts

Note: At implementation time in this worktree, explicit Product/System Architecture spec files were not present. This document defines conservative contracts that avoid contradicting accepted decisions and can be tightened once dependency specs are materialized.

## Output 1: Entity List

### 1) HarnessIdentity
Purpose: Represents a user-owned harness that can request work or execute work.

Fields:
- `harness_id` (string, stable id, PK)
- `owner_user_id` (string)
- `display_name` (string)
- `public_key` (string)
- `status` (enum: `active|paused|revoked`)
- `created_at` (ISO timestamp)
- `updated_at` (ISO timestamp)

### 2) WorkRequest
Purpose: A normalized request from requester harness to worker harness.

Fields:
- `request_id` (string, PK)
- `requester_harness_id` (string, FK -> HarnessIdentity)
- `target_harness_id` (string, FK -> HarnessIdentity)
- `task_type` (string)
- `task_payload_json` (JSON string)
- `constraints_json` (JSON string, optional)
- `priority` (integer, default 0)
- `status` (enum: `draft|queued|accepted|in_progress|completed|failed|cancelled`)
- `idempotency_key` (string, unique)
- `created_at` (ISO timestamp)
- `updated_at` (ISO timestamp)

### 3) WorkAssignment
Purpose: Binds a request to execution context on the worker harness.

Fields:
- `assignment_id` (string, PK)
- `request_id` (string, FK -> WorkRequest)
- `worker_harness_id` (string, FK -> HarnessIdentity)
- `lease_expires_at` (ISO timestamp, optional)
- `attempt` (integer)
- `status` (enum: `assigned|running|succeeded|failed|abandoned`)
- `created_at` (ISO timestamp)
- `updated_at` (ISO timestamp)

### 4) WorkResult
Purpose: Durable result summary and output pointer for completed work.

Fields:
- `result_id` (string, PK)
- `request_id` (string, FK -> WorkRequest)
- `assignment_id` (string, FK -> WorkAssignment)
- `outcome` (enum: `success|partial|failure`)
- `result_payload_json` (JSON string)
- `error_code` (string, optional)
- `error_message` (string, optional)
- `completed_at` (ISO timestamp)
- `created_at` (ISO timestamp)

### 5) EventLog
Purpose: Append-only audit/event stream supporting runtime replay and CLI inspection.

Fields:
- `event_id` (string, PK)
- `request_id` (string, optional FK -> WorkRequest)
- `assignment_id` (string, optional FK -> WorkAssignment)
- `event_type` (string)
- `event_payload_json` (JSON string)
- `occurred_at` (ISO timestamp)

### 6) RuntimeCheckpoint
Purpose: Persisted marker for safe restart/replay behavior.

Fields:
- `checkpoint_id` (string, PK)
- `harness_id` (string, FK -> HarnessIdentity)
- `last_processed_event_id` (string)
- `last_sync_at` (ISO timestamp)
- `created_at` (ISO timestamp)
- `updated_at` (ISO timestamp)

## Output 2: State Ownership

### Domain/Core State Owner
Module: `domain` (or equivalent core logic module)

Owns:
- Lifecycle rules and transitions for `WorkRequest`, `WorkAssignment`, `WorkResult`
- Status transition guards (for example `queued -> accepted -> in_progress -> completed`)
- Idempotency rules by `idempotency_key`

Does not own:
- Transport details (CLI parsing, network protocol framing)
- SQLite connection/session lifecycle

### Runtime/Orchestration State Owner
Module: `runtime`

Owns in-memory session state:
- `current_harness_id`
- Active command context (CLI)
- Pending outbound message queue (transient)
- Retry/backoff counters (transient)

Writes via domain interfaces:
- New `WorkRequest`
- `WorkAssignment` status updates
- `EventLog` records for key transitions

### Persistence State Owner
Module: `persistence` (SQLite adapter)

Owns:
- Table schema mappings for entities above
- Read/write transactions
- Query projections for CLI views (queue, active work, history)

Does not own:
- Business transition validity
- Command semantics

## Output 3: Persistence Data Contract (SQLite)

## Canonical storage
- SQLite is the source of truth for all durable entities.
- JSON fields are stored as text and validated by domain before persistence.
- Timestamps are stored in UTC ISO-8601 text.

## Minimum table set
- `harness_identity`
- `work_request`
- `work_assignment`
- `work_result`
- `event_log`
- `runtime_checkpoint`

## Required keys and constraints
- Primary keys on all `*_id` fields listed above.
- Foreign keys from request/assignment/result/event/checkpoint relations as defined in entity list.
- Unique index on `work_request.idempotency_key`.
- Indexes:
  - `work_request(status, created_at)`
  - `work_assignment(status, updated_at)`
  - `event_log(occurred_at)`

## Save/load contract
Save operations must:
- Validate domain transition before write.
- Write transition + event log atomically in one transaction.
- Return persisted record ids and final statuses.

Load operations must:
- Support CLI queries for pending, active, and historical work.
- Support restart flow by loading `runtime_checkpoint` + unfinalized assignments.

## Runtime handoff compatibility
Runtime-to-domain handoff payload shape (conceptual):
- `SubmitWorkInput`:
  - `requester_harness_id`
  - `target_harness_id`
  - `task_type`
  - `task_payload`
  - `idempotency_key`

Domain-to-persistence handoff shape (conceptual):
- `PersistWorkRequestCommand`:
  - normalized request fields
  - initial status
  - event metadata for append to `event_log`

Persistence-to-runtime read model shape (conceptual):
- `WorkQueueItem`:
  - `request_id`
  - `task_type`
  - `status`
  - `priority`
  - `updated_at`

## Compatibility Rules
- Entity field removals or type changes are breaking changes and require interface-change approval.
- New optional fields are backward compatible if defaultable.
- Enum expansion is allowed only when runtime and CLI rendering provide unknown-value fallback.

## Risks and Assumptions
- Assumption: Product/System specs will not introduce a conflicting identity model; if they do, this spec needs reconciliation.
- Risk: Without final API contract spec, event payload schemas remain intentionally coarse-grained (`*_payload_json`).
- Mitigation: Keep payload envelopes stable (`request_id`, `assignment_id`, `event_type`) and version payload internals if needed.
