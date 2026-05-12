# Hardware Abstraction Plan (Raspberry Pi v1, ESP32 Companion-Ready)

## 1. Purpose

Defines adapter boundaries so v1 ships on Raspberry Pi without coupling core services to Pi-specific APIs, while preserving a clean path for future ESP32 companion integration.

## 2. Adapter Layers

Core services (`RuntimeService`, `CaptureService`, `TriggerService`, `StorageService`) depend only on abstract ports.

Concrete adapters are selected by runtime profile.

```text
Core Services
  -> CameraPort
  -> ImuPort
  -> FileSystemPort
  -> ClockPort
  -> PowerPort
  -> CompanionPort (optional in v1)
```

## 3. CameraPort

Responsibilities:

- Enumerate single front camera source.
- Configure stream to 720p/30.
- Deliver encoded or raw frames to capture pipeline.

Contract shape:

- `open(config) -> CameraSession | Error`
- `readFrame(timeoutMs) -> Frame | Timeout | Error`
- `close(sessionId) -> Result`
- `health() -> CameraHealth`

Pi v1 concrete expectation:

- V4L2/libcamera-based adapter.

## 4. ImuPort

Responsibilities:

- Poll or interrupt-driven acceleration sample ingest.
- Timestamp sample with monotonic clock at adapter boundary.
- Provide calibration support.

Contract shape:

- `start(sampleRateHz) -> Result`
- `readSample() -> ImuSample | Error`
- `calibrate(windowSec) -> CalibrationResult`
- `health() -> ImuHealth`

Pi v1 concrete expectation:

- I2C/SPI IMU adapter bound to selected sensor module.

## 5. FileSystemPort

Responsibilities:

- Atomic rename and durability hints (`fsync`/flush semantics).
- Directory enumeration and capacity metrics.
- Safe delete and quota-aware free-space queries.

Contract shape:

- `writeTemp(segmentId, bytes) -> TempHandle`
- `commitTemp(tempHandle, finalPath) -> Result`
- `delete(path) -> Result`
- `statCapacity() -> CapacityInfo`
- `listSegments() -> SegmentFileInfo[]`

## 6. ClockPort

Responsibilities:

- Monotonic timestamp source for all event and segment ordering.
- Optional wall-clock mapping for user-facing metadata.

Contract shape:

- `nowMonoNs() -> int64`
- `nowWallUtcMs() -> int64`

## 7. PowerPort

Responsibilities:

- Signal ignition/power state transitions if available.
- Provide low-voltage or imminent shutdown notice.

Contract shape:

- `subscribePowerEvents(callback)`
- `lastKnownState() -> PowerState`

v1 fallback:

- If no hardware signal exists, runtime uses periodic flush and watchdog-safe shutdown heuristics.

## 8. CompanionPort (Future ESP32 Helper)

v1 policy:

- Optional and disabled by default; must not be required for capture pipeline operation.

Future role:

- ESP32 may act as sensor hub, power-state proxy, or watchdog supervisor.

Minimal future contract:

- `connect() -> Result`
- `recv() -> CompanionMessage`
- `send(Command) -> Result`

Candidate transport:

- UART primary, CAN optional for vehicle-grade variants.

Message classes for future compatibility:

- `imu_sample`
- `power_event`
- `heartbeat`
- `watchdog_kick_request`

## 9. Porting Rules

- Core services must not import Pi-specific libraries directly.
- All hardware-specific retries are handled in adapter layer or runtime policy, not in domain logic.
- Adapter errors are normalized to shared error codes defined in `contracts/dashcam-service-contracts.md`.

## 10. Risk Notes and Mitigations

Power loss:

- Mitigation: `PowerPort` early warning when available; otherwise short segment size plus frequent flush.

Storage corruption:

- Mitigation: `FileSystemPort` enforces atomic commit and explicit sync points.

Sensor noise:

- Mitigation: `ImuPort` calibration and trigger-service debounce/hysteresis.
