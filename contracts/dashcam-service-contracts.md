# Dashcam Service Contracts (v1)

## 1. Contract Scope

This file is the cross-module contract baseline for v1 and is owned by architecture/planner.

It specifies:

- Service APIs and event payloads.
- Shared data models.
- Error semantics and idempotency rules.

## 2. Shared Types

### Enums

- `Severity = INFO | WARN | ERROR | CRITICAL`
- `Subsystem = RUNTIME | CAPTURE | TRIGGER | STORAGE | HARDWARE`
- `EventType = IMPACT_G`
- `ServiceState = BOOT | READY | RECORDING | DEGRADED | PAUSED_STORAGE_PROTECTED`

### Struct: `SegmentMeta`

- `segmentId: string`
- `cameraId: string` (v1 fixed `front-0`)
- `startMonoNs: int64`
- `endMonoNs: int64`
- `durationMs: int32`
- `bytes: int64`
- `codec: string` (v1 `h264`)
- `resolution: string` (v1 `1280x720`)
- `fps: int32` (v1 `30`)
- `checksum: string`

### Struct: `ImpactEvent`

- `eventId: string` (UUID or monotonic-unique key)
- `eventType: EventType`
- `triggerTsMonoNs: int64`
- `magnitudeG: float`
- `confidence: float` (`0.0..1.0`)
- `source: string` (v1 `imu-local`)
- `preSec: int32`
- `postSec: int32`

### Struct: `ServiceError`

- `code: string`
- `message: string`
- `subsystem: Subsystem`
- `retryable: bool`
- `tsMonoNs: int64`

## 3. RuntimeService Contract

Responsibilities:

- Lifecycle orchestration.
- Health/alarm publication.
- Config distribution.

API:

- `Boot(configPath) -> Result<RuntimeReady, ServiceError>`
- `StartRecording() -> Result<ServiceState, ServiceError>`
- `StopRecording(reason) -> Result<ServiceState, ServiceError>`
- `ApplyConfig(partialConfig, expectedVersion) -> Result<ConfigVersion, ServiceError>`
- `GetHealth() -> HealthSnapshot`

Published events:

- `HealthEvent { severity, subsystem, code, detail, tsMonoNs }`
- `StateChanged { previous, current, reason, tsMonoNs }`

Runtime error behavior:

- Must downgrade to degraded states instead of process exit when recovery is possible.
- Must propagate normalized `ServiceError` from downstream services without lossy remapping.

## 4. CaptureService Contract

Responsibilities:

- Camera ingest + encoding.
- Segment close notifications.

API:

- `StartCapture(CaptureConfig) -> Result<CaptureSession, ServiceError>`
- `StopCapture(sessionId) -> Result<void, ServiceError>`
- `GetCaptureStats() -> CaptureStats`
- `FlushSegment(sessionId, maxWaitMs) -> Result<SegmentMeta, ServiceError>`

Input type: `CaptureConfig`

- `cameraId: string` (v1 required `front-0`)
- `width: int32` (v1 `1280`)
- `height: int32` (v1 `720`)
- `fps: int32` (v1 `30`)
- `segmentSec: int32` (default `60`)
- `targetBitrateMbps: float`

Published events:

- `SegmentClosed { meta: SegmentMeta, tempPath: string, tsMonoNs }`
- `CaptureFault { error: ServiceError, sessionId }`

Capture error behavior:

- On transient camera read failure, capture may retry internally up to configured threshold.
- On persistent failure, emit `CaptureFault` and return control to runtime.

## 5. TriggerService Contract

Responsibilities:

- IMU sampling pipeline.
- Impact event generation.

API:

- `ArmTrigger(TriggerConfig) -> Result<void, ServiceError>`
- `DisarmTrigger() -> Result<void, ServiceError>`
- `IngestSample(ImuSample) -> Result<Optional<ImpactEvent>, ServiceError>`
- `GetTriggerStats() -> TriggerStats`

Input type: `TriggerConfig`

- `sampleRateHz: int32`
- `impactThresholdG: float`
- `debounceMs: int32`
- `minConfidence: float`

Input type: `ImuSample`

- `tsMonoNs: int64`
- `ax: float`
- `ay: float`
- `az: float`
- `temperatureC: float?`

Published events:

- `ImpactDetected { event: ImpactEvent }`
- `TriggerFault { error: ServiceError }`

Trigger error behavior:

- Sample parse faults are counted and dropped; service continues.
- Adapter disconnect emits non-retryable fault until runtime restarts adapter.

## 6. StorageService Contract

Responsibilities:

- Segment persistence and index.
- Ring reclaim and event-lock enforcement.

API:

- `Initialize(StorageConfig) -> Result<StorageReady, ServiceError>`
- `PersistSegment(meta: SegmentMeta, tempPath: string) -> Result<PersistResult, ServiceError>`
- `CreateEventLock(event: ImpactEvent) -> Result<EventLockResult, ServiceError>`
- `ClearEventLock(eventId: string) -> Result<ClearResult, ServiceError>`
- `ReclaimIfNeeded() -> Result<ReclaimResult, ServiceError>`
- `GetRetentionStatus() -> RetentionSnapshot`

Input type: `StorageConfig`

- `capacityGiB: int32` (v1 `<= 1024`)
- `systemReserveGiB: float`
- `safetyReserveGiB: float`
- `metadataReserveGiB: float`
- `lockQuotaGiB: float`
- `loopQuotaGiB: float`

Output type: `EventLockResult`

- `eventId: string`
- `windowStartMonoNs: int64`
- `windowEndMonoNs: int64`
- `lockedSegmentIds: string[]`
- `lockBytesAdded: int64`
- `quotaExceeded: bool`

Published events:

- `SegmentIndexed { segmentId, bytes, tsRange }`
- `EventLockApplied { eventId, lockedSegmentIds }`
- `StorageFault { error: ServiceError }`

Storage error behavior:

- `PersistSegment` is atomic: either visible in index and on disk, or absent from both after recovery.
- `CreateEventLock` is idempotent by `eventId`.
- If lock quota would be exceeded after cleanup attempts, return `ERR_LOCK_QUOTA_EXCEEDED` without partial lock writes.

## 7. Cross-Service Interaction Contract

Required event routing:

- `CaptureService.SegmentClosed` -> `StorageService.PersistSegment`
- `TriggerService.ImpactDetected` -> `StorageService.CreateEventLock` (through runtime orchestrator)
- `StorageService.StorageFault` -> `RuntimeService` state/alarm handler

Ordering guarantees:

- Runtime submits lock requests in non-decreasing `triggerTsMonoNs` order.
- Storage must support late-arriving lock requests referencing already-written segments.

## 8. Normalized Error Codes

Global error code set used across services:

- `ERR_CAMERA_UNAVAILABLE`
- `ERR_CAMERA_STREAM_LOST`
- `ERR_ENCODER_BACKPRESSURE`
- `ERR_IMU_UNAVAILABLE`
- `ERR_IMU_SAMPLE_INVALID`
- `ERR_MEDIA_UNAVAILABLE`
- `ERR_MEDIA_READ_ONLY`
- `ERR_JOURNAL_CORRUPT`
- `ERR_INDEX_CORRUPT`
- `ERR_LOCK_QUOTA_EXCEEDED`
- `ERR_NO_UNLOCKED_SEGMENTS`
- `ERR_CONFIG_INVALID`
- `ERR_DEPENDENCY_NOT_READY`

Error handling contract:

- All errors must include `retryable` classification.
- Runtime retries only retryable errors with bounded backoff.
- Non-retryable critical errors transition runtime into protected state and raise alarm.

## 9. Reliability Contract Clauses

Power loss:

- Services must assume abrupt termination at any instruction boundary.
- Storage journal replay must restore index and lock references before reclaim resumes.

Storage corruption:

- If checksum mismatch on segment file, storage quarantines segment and logs fault.
- Quarantined segments are not auto-deleted until operator clears fault.

Sensor noise:

- Trigger must apply debounce and confidence thresholds before publishing `ImpactDetected`.
- Repeated sub-threshold spikes must not generate lock events.
