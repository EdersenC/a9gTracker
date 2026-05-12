# Dashcam v1 Architecture Overview

## 1. Scope and Decision Traceability

This document defines the v1 technical architecture for WorkflowGraph `workflow-project-46-orchestration-7` rev 8.

Resolved decisions mapped to architecture:

| Workflow decision | Architecture implication |
| --- | --- |
| Raspberry Pi first | Runtime, capture, trigger, and storage run on Raspberry Pi as the primary controller. |
| Offline local only | No cloud sync, no remote APIs, no cellular/Wi-Fi dependencies in runtime critical path. |
| 720p/30fps loop + event lock | Capture service continuously records segmented video and storage service enforces ring overwrite with event protection. |
| Single front camera | Exactly one camera ingest pipeline in v1. Interfaces still support future multi-channel extension. |
| G-sensor trigger | Trigger service consumes IMU samples and emits impact events with confidence and timestamp. |
| Retention user-configurable up to 1TB | Storage profile is configurable by installed media and policy; supports capacities up to 1TB. |
| Default shipped/validation profile 1TB | Performance and soak targets are validated on 1TB default profile. |

## 2. System Context

Single-device, on-vehicle system:

- One front camera source.
- One IMU/G-sensor source.
- Local storage media (default profile validated on 1TB).
- No network dependency for record/lock/recover flows.

Core services are process-level modules with strict contracts:

- `RuntimeService`: startup, configuration, orchestration, health, degraded-mode decisions.
- `CaptureService`: camera ingest, 720p/30 encoding, fixed-duration segment emission.
- `TriggerService`: impact detection from IMU stream and event decision generation.
- `StorageService`: ring buffer indexing, retention policy, lock protection, recovery on restart.

## 3. Module Boundaries

### RuntimeService (orchestrator)

Owns:

- Boot sequence and dependency readiness checks.
- Service lifecycle and state transitions.
- Configuration loading/validation.
- Fault policy (retry, degrade, fail-safe states).

Does not own:

- Video encoding internals.
- IMU filtering internals.
- File-level overwrite logic.

### CaptureService

Owns:

- Camera adapter binding and stream setup.
- Encoder configuration to 720p/30fps target.
- Segment finalization and metadata generation.

Does not own:

- Segment retention/overwrite decisions.
- Trigger logic.

### TriggerService

Owns:

- IMU calibration offsets and noise filtering.
- Impact threshold and hysteresis logic.
- Trigger event emission (`ImpactEvent`).

Does not own:

- Direct file locking.
- Capture lifecycle.

### StorageService

Owns:

- Segment index journal and integrity checks.
- Ring buffer candidate selection and reclamation.
- Event window locking and overlap handling.
- Retention quotas per configured storage profile.

Does not own:

- Sensor interpretation.
- Encoding decisions.

## 4. Data and Control Flow (High-Level)

1. `RuntimeService` starts adapters and services.
2. `CaptureService` emits completed segments at fixed duration.
3. `StorageService` indexes segment and applies ring policy.
4. `TriggerService` emits impact event from IMU stream.
5. `RuntimeService` forwards event to `StorageService` to lock matching pre/post window segments.
6. `StorageService` updates event and lock indexes; future reclaim excludes locked segments.

Detailed sequence/state flow is specified in `docs/architecture/event-pipeline.md`.

## 5. Non-Functional Targets

### Performance

- Sustained capture: `1280x720 @ 30fps` continuous for 24h on Raspberry Pi baseline profile.
- Segment close-to-index latency (P95): <= 250 ms.
- Trigger-to-lock decision latency (P95): <= 500 ms from impact sample timestamp.
- Trigger timestamp skew vs monotonic clock: <= 100 ms after time sync at boot.

### Storage

- Must support up to `1TB` installed media in v1 policy engine.
- Ring overwrite must never delete segments with active lock references.
- Metadata/index overhead target: <= 2% of media.

### Reliability

- Clean restart after power loss without full media scan when journal intact.
- Journal recovery path must restore lock state before overwrite resumes.
- No network requirement for any safety-critical path.

## 6. Failure and Degraded Modes

- Camera unavailable at boot: runtime enters `DEGRADED_NO_CAPTURE`, retries with backoff.
- IMU unavailable: runtime may continue recording but marks trigger subsystem degraded.
- Storage near exhaustion with fully locked pool: runtime pauses overwrite, raises `ERR_NO_UNLOCKED_SEGMENTS`, and preserves locked evidence.
- Journal corruption: storage enters recovery scan and blocks overwrite until lock map is reconstructed.

## 7. Out of Scope (v1)

- Cloud sync, remote live view, or OTA control plane.
- Multi-camera stitching.
- ESP32-as-primary recorder mode.

## 8. Implementation Handoff Notes

- `contracts/dashcam-service-contracts.md` is the contract source of truth for sibling implementation agents.
- Module teams should consume contracts and avoid redefining cross-service message schemas.
- Hardware abstractions for Pi and future companion paths are defined in `docs/architecture/hardware-abstraction.md`.
