# Database/Persistence Spec (Task #6)

## Scope
This spec defines v1 persistence boundaries for the CLI/text runtime and provides the required outputs for downstream Data Architecture and Runtime Flow consumers.

## Persistence Need (Explicit)
Persistence is required in v1.

Rationale:
- The product needs durable cross-session state for a two-party network where one user's AI harness can perform work for another harness.
- CLI runtime restarts are expected; in-memory-only state would lose task/work records, peer relationship metadata, and execution history.
- Basic reliability and operability require resumable state after process exit or crash.

## Storage Strategy Decision
Decision: SQLite is the v1 persistence store.

Rationale:
- Accepted architecture decision mandates SQLite.
- Fits CLI/text deployment: embedded, zero external service dependency, local file durability.
- Provides transactional guarantees (ACID) needed for task/workflow state transitions.
- Simple operational model for v1 and easy local debugging.

Alternatives considered (not selected):
- JSON file storage: easy start, but weak concurrency guarantees, brittle schema evolution, and high corruption risk on partial writes.
- External DB (e.g., Postgres): stronger multi-client scaling, but adds infra/ops complexity outside v1 scope.

## Persistence Contract
Owner: `database` module
Consumers: Data Architecture Spec, Runtime Flow Spec

Contract:
- The persistence layer owns durable state lifecycle: initialize, read, write, update, and query durable entities.
- All durable writes occur through repository/store interfaces, not direct file mutation.
- Writes for logically-coupled updates MUST be transactional.
- Runtime logic remains storage-agnostic and depends on persistence interfaces only.
- Database file location is environment-configurable with a stable default (project-local SQLite file).
- Schema version is tracked in-database; startup performs version check before runtime loop begins.

Boundary rules:
- Durable: peer identity references, work/task records, task state transitions, timestamps/audit trail needed for resume.
- Ephemeral/in-memory: transient CLI rendering state, short-lived network/session objects, retry backoff timers.

## Save/Load Acceptance Criteria
1. On first run, system initializes SQLite DB and required schema without manual setup.
2. On subsequent runs, previously saved durable entities are loadable and consistent.
3. Task/work state changes are persisted atomically; partial state transition writes are not observable after failure.
4. Process restart after graceful shutdown preserves all committed records.
5. Process restart after abrupt termination preserves last committed transaction (no invalid half-written rows).
6. If DB file is missing, system recreates schema and starts cleanly.
7. If schema version mismatch is detected, startup exits with a clear migration-required error (no silent auto-mutation unless migration path is defined).
8. Persistence interfaces expose deterministic load behavior required by runtime startup sequence.

## Migration and File-Format Risk
Risks in scope:
- Schema evolution risk: changing entity shape may break older DB files.
- Single-file DB contention risk if future architecture introduces parallel writers.
- Corruption risk from uncontrolled external file edits.

Mitigations:
- Enforce schema version table and explicit migration steps.
- Keep all writes in transactions; use SQLite journaling defaults suitable for crash recovery.
- Restrict DB writes to persistence module interfaces.
- Add startup integrity checks and actionable error messages.

## Non-Goals (v1)
- Multi-node distributed consensus across replicas.
- Live online schema migration with zero downtime.
- External managed database infrastructure.

## Downstream Interface Outputs
- `database:Persistence contract`: Defined in "Persistence Contract" section.
- `database:Storage strategy decision`: SQLite with explicit rationale in "Storage Strategy Decision" section.
- `database:Save/load acceptance criteria`: Defined in "Save/Load Acceptance Criteria" section.
