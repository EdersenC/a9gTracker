# System Architecture Spec (Orchestration #6, Task #2)

## Scope and constraints
- SpecContainer: `system_architecture`
- Goal context: a 2-party network where personal AI harnesses can do work for other harnesses
- Accepted decisions:
  - Persistence strategy: SQLite
  - Runtime/UI target: CLI/text
- This document defines boundaries only; it does not change runtime flow, data schema, or API payload definitions owned by other specs.

## Module boundaries

### 1) `cli_adapter`
Owns all text UI and command parsing.
- Responsibilities:
  - Render prompts, status, errors, and task results in terminal output
  - Parse user commands into domain-level intents
  - Forward intents to orchestrator services
- Must not:
  - Contain business rules for matching, scheduling, or trust policy
  - Access SQLite directly

### 2) `session_application`
Owns top-level application lifecycle and use-case orchestration.
- Responsibilities:
  - Boot app components and wire dependencies
  - Coordinate user session actions (register harness, post work, claim work, complete work, inspect status)
  - Translate domain outcomes to presenter-friendly view models for `cli_adapter`
- Must not:
  - Implement low-level transport/storage protocols

### 3) `harness_domain`
Owns core business logic for two-party harness interactions.
- Responsibilities:
  - Validate harness identity and participation rules
  - Enforce task lifecycle invariants (created -> assigned -> in_progress -> completed/failed)
  - Enforce cross-harness trust/permission checks
  - Resolve which harness can accept or execute a work item
- Must not:
  - Read terminal I/O
  - Issue SQL statements

### 4) `work_exchange_domain`
Owns marketplace/exchange behavior for work between harnesses.
- Responsibilities:
  - Manage work offer visibility and claimability
  - Apply matching and prioritization policies
  - Produce domain events for state transitions
- Must not:
  - Depend on CLI formatting or SQLite schema details

### 5) `persistence_port`
Owns storage abstractions used by domain/application modules.
- Responsibilities:
  - Define repository interfaces and transaction boundary contracts
  - Define save/load semantics for sessions, harnesses, and work items
- Must not:
  - Contain SQLite-specific SQL

### 6) `sqlite_adapter`
Owns concrete persistence implementation via SQLite.
- Responsibilities:
  - Implement repository interfaces from `persistence_port`
  - Map domain entities to relational rows
  - Handle migrations/bootstrap checks needed by v1
- Must not:
  - Host business decisions or CLI behavior

### 7) `network_port`
Owns abstract harness-to-harness communication contract.
- Responsibilities:
  - Define message send/receive operations, retries, timeout semantics, and delivery acknowledgments
  - Provide a seam so runtime flow can evolve from local simulation to real networked transport
- Must not:
  - Encode transport-specific protocol internals

### 8) `network_adapter`
Owns concrete transport implementation (initially local/simulated transport suitable for CLI v1).
- Responsibilities:
  - Implement `network_port`
  - Serialize/deserialize message envelopes and hand off payloads to application layer
- Must not:
  - Make trust, scheduling, or task-state business decisions

## Dependency map
- `cli_adapter` -> `session_application`
- `session_application` -> `harness_domain`
- `session_application` -> `work_exchange_domain`
- `session_application` -> `persistence_port`
- `session_application` -> `network_port`
- `sqlite_adapter` implements `persistence_port`
- `network_adapter` implements `network_port`
- `harness_domain` and `work_exchange_domain` are pure-domain modules; they depend only on shared domain primitives/contracts.

## Integration contracts

### Contract A: CLI to Application
- Input: parsed command intents with minimal validated syntax.
- Output: result object (`success|error`, message key, optional payload for rendering).
- Ownership:
  - Command grammar: `cli_adapter`
  - Use-case semantics: `session_application`

### Contract B: Application to Domain
- Input: explicit command/use-case objects (no raw CLI text).
- Output: domain result + domain events.
- Ownership:
  - Use-case sequencing: `session_application`
  - Invariants and policy checks: `harness_domain` / `work_exchange_domain`

### Contract C: Domain/Application to Persistence
- Input: entity persistence requests through repository interfaces.
- Output: loaded entities, save acknowledgments, conflict errors.
- Ownership:
  - Repository interface + transactional expectations: `persistence_port`
  - SQL mapping + DB lifecycle: `sqlite_adapter`

### Contract D: Application to Network
- Input: outbound work exchange messages and correlation metadata.
- Output: delivery status + inbound message callbacks/events.
- Ownership:
  - Message semantic meaning: `session_application` + domains
  - Delivery mechanics/timeouts/retries: `network_port` + `network_adapter`

### Contract E: Shared Validation seam
- Validation split:
  - Syntax/input shape checks at `cli_adapter`
  - Business rule validation at domain modules
  - Persistence integrity checks at `sqlite_adapter`
- Rule: shared behavior is single-owned at the lowest correct boundary; no duplicated validation logic across layers.

## Shared behavior ownership
- Task lifecycle state machine: `harness_domain`
- Work matchmaking/claim policy: `work_exchange_domain`
- Session orchestration and cross-module transaction boundaries: `session_application`
- Human-readable output rendering and command UX: `cli_adapter`
- Durable state storage details: `sqlite_adapter`
- Inter-harness delivery/retry mechanics: `network_adapter`

## Future file ownership hints

Suggested implementation-aligned layout:
- `docs/specs/system_architecture_spec.md` (owned by system architecture updates)
- `src/cli/` -> `cli_adapter`
- `src/app/session/` -> `session_application`
- `src/domain/harness/` -> `harness_domain`
- `src/domain/work_exchange/` -> `work_exchange_domain`
- `src/ports/persistence/` -> `persistence_port`
- `src/adapters/sqlite/` -> `sqlite_adapter`
- `src/ports/network/` -> `network_port`
- `src/adapters/network/` -> `network_adapter`

Ownership guidance for future agents:
- Domain agents own `src/domain/**` and must not import adapter packages.
- Adapter agents own `src/adapters/**` and must satisfy contracts in `src/ports/**`.
- Runtime/application agents own `src/app/**` orchestration and dependency wiring.
- CLI/UI agents own `src/cli/**` without embedding domain policy logic.

## Acceptance criteria check
- Major modules and dependencies are named: satisfied via Module boundaries + Dependency map.
- Shared behavior is owned by a clear module: satisfied via Shared behavior ownership section.
