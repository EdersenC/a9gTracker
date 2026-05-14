# API/Interface Contract Spec (api_contract)

Status: needs_review  
Owner: API/Interface Contract Spec Agent (Agent 7)  
Consumers: System Architecture Spec, Runtime Flow Spec, future child implementation agents

## Scope
Defines shared module/API/event contracts for a CLI-based runtime where personal AI harnesses can send work requests to peer harnesses. This spec is the source of truth for:
- Interface list
- Payload ownership
- Compatibility rules

Accepted architecture constraints:
- Persistence strategy: SQLite
- Runtime/UI target: CLI/text

## Interface List

### 1) Runtime Orchestrator Interface
Producer: `runtime_flow` implementation  
Consumers: CLI adapter, network adapter, update flow

Methods:
- `boot(config: BootConfig) -> BootResult`
- `handleInput(cmd: CliCommandEnvelope) -> RuntimeAction[]`
- `handleEvent(event: EventEnvelope) -> RuntimeAction[]`
- `tick(nowMs: int) -> RuntimeAction[]`
- `shutdown(reason: ShutdownReason) -> ShutdownResult`

Contract notes:
- Runtime orchestrator is the only writer of in-memory session state.
- All external signals (CLI or network) must enter through envelope-based handlers.

### 2) Network Client Interface
Producer: `system_architecture` network module  
Consumers: runtime orchestrator

Methods:
- `connect(peer: PeerDescriptor) -> ConnectionResult`
- `send(req: WorkRequestEnvelope) -> SendResult`
- `poll(timeoutMs: int) -> EventEnvelope[]`
- `close(peerId: string) -> CloseResult`

Contract notes:
- Transport details (cellular/socket/TLS) are hidden from runtime orchestrator.
- Network module must only emit normalized `EventEnvelope` objects.

### 3) Persistence Repository Interface
Producer: persistence module (SQLite-backed)  
Consumers: runtime orchestrator, update flow

Methods:
- `loadNodeState(nodeId: string) -> NodeStateRecord`
- `saveNodeState(state: NodeStateRecord) -> SaveResult`
- `appendWorkLog(entry: WorkLogRecord) -> SaveResult`
- `listPendingWork(limit: int) -> WorkItemRecord[]`
- `markWorkStatus(workId: string, status: WorkStatus) -> SaveResult`

Contract notes:
- SQLite schema is owned by persistence slice; this interface is the only runtime access path.
- Repository methods are atomic per call.

### 4) Update Transfer Interface
Producer: update module  
Consumers: runtime orchestrator

Methods:
- `requestUpdate(meta: UpdateRequestEnvelope) -> UpdateInstructionEnvelope`
- `requestChunk(cursor: ChunkCursorEnvelope) -> UpdateChunkEnvelope`
- `verifyChunk(chunk: UpdateChunkEnvelope) -> ChunkVerificationResult`
- `completeUpdate(finalize: UpdateFinalizeEnvelope) -> UpdateCompletionEnvelope`

Contract notes:
- Chunk transfer is resumable and checksum-gated.
- Runtime never writes update files directly without checksum verification.

### 5) CLI Command Adapter Interface
Producer: CLI/text UI module  
Consumers: runtime orchestrator

Methods:
- `readCommand() -> CliCommandEnvelope`
- `renderStatus(view: StatusViewModel) -> void`
- `renderError(err: ErrorViewModel) -> void`

Contract notes:
- CLI module is responsible for parsing raw user text into typed command envelopes.
- Runtime module is responsible for command semantics.

## Payload Ownership

### Canonical Envelopes (owned by api_contract)
All cross-module messages must use these envelope shapes:
- `EventEnvelope`
- `CliCommandEnvelope`
- `WorkRequestEnvelope`
- `WorkResponseEnvelope`
- `RuntimeActionEnvelope`
- `UpdateInstructionEnvelope`
- `UpdateChunkEnvelope`

Envelope minimum fields:
- `schemaVersion: string`
- `eventType | commandType | actionType: string`
- `requestId: string`
- `timestampMs: int`
- `sourceNodeId: string`
- `targetNodeId?: string`
- `payload: object`

### Field-Level Ownership
- `runtime_flow` owns: action semantics, state transition requirements, error categories.
- `system_architecture` owns: adapter boundaries and module dependency direction.
- `data_architecture` owns: record/entity payloads under `payload` for persisted domain state.
- `database` owns: SQLite persistence representation and save/load invariants.
- `ui_flow` owns: CLI command vocabulary and view-model fields.
- `api_contract` owns: envelope wrappers, required metadata fields, and compatibility policy.

### Consumer Matrix
- `system_architecture` consumes interface signatures and ownership boundaries.
- `runtime_flow` consumes event/command/action envelope definitions.
- Future implementation agents consume this file as source-of-truth for any shared payload or interface integration.

## Compatibility Rules

### Versioning
1. Envelope-level compatibility follows semantic versioning in `schemaVersion`.
2. Additive field changes within existing envelope payloads are backward-compatible when fields are optional.
3. Removing or renaming required fields is a breaking change.

### Change Control
1. Any change to shared interface signatures or envelope required fields requires `request_interface_change` approval before merge.
2. Producers and consumers must support one adjacent minor version during rollouts (`N` and `N-1` minor).
3. Breaking changes require a migration note listing impacted consumers (`system_architecture`, `runtime_flow`, and implementation children).

### Runtime Safety
1. Unknown optional fields must be ignored by consumers.
2. Unknown required fields for newer versions must trigger `IncompatibleSchema` error.
3. Missing required fields must trigger `InvalidEnvelope` error and no state mutation.
4. Duplicate `requestId` in persistence-backed workflows must be idempotent (no duplicate side-effects).

### Persistence/Transport Constraints
1. Integer timestamps use epoch milliseconds.
2. Checksum fields are string-encoded to avoid integer-size variance across runtimes.
3. SQLite persistence writes must not depend on field order in JSON payload serialization.

## Validation Notes
- Validation commands: none provided in AgentWorkContract.
- This is a spec-only update; no runtime code, schema, or route mutations were applied.

## Handoff Notes
- Future child-agent contracts should quote this file for interface names and envelope ownership.
- If runtime or system modules require contract shape changes, raise `request_interface_change` first.
