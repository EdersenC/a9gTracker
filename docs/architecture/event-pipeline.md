# Event Pipeline Specification (v1)

## 1. Purpose

Defines message flow and state transitions between runtime, capture, trigger, and storage services for loop recording and impact-triggered event locking.

## 2. Time and Segment Model

- Clock source for cross-service ordering: monotonic clock provided by runtime.
- Segment duration (`SEGMENT_SEC`): 60 seconds (configurable, default 60).
- Segment identity: `cameraId + startMonoNs + sequence`.
- Event window defaults: `PRE_EVENT_SEC = 15`, `POST_EVENT_SEC = 45`.

Event windows are mapped to whole segments by intersection rule:

- A segment is lock-eligible if its `[segmentStart, segmentEnd)` intersects event window `[eventTs - PRE_EVENT_SEC, eventTs + POST_EVENT_SEC]`.
- Partial overlap locks the whole segment.

## 3. Continuous Loop Sequence

```text
RuntimeService -> CaptureService: StartCapture(config: 720p/30, segment=60s)
CaptureService -> StorageService: SegmentClosed(meta, tempFilePath)
StorageService -> StorageService: Validate segment + compute checksum
StorageService -> StorageService: Move into ring namespace + append journal
StorageService -> RuntimeService: SegmentIndexed(segmentId, bytes, tsRange)
RuntimeService -> RuntimeService: Update health metrics
```

Error branch:

```text
CaptureService -> RuntimeService: CaptureFault(code, detail)
RuntimeService -> CaptureService: RestartCapture(backoff policy)
RuntimeService -> StorageService: EmitHealthEvent(subsystem=capture,degraded=true)
```

## 4. Impact Trigger Sequence

```text
TriggerService -> TriggerService: IngestImuSample(ax,ay,az,ts)
TriggerService -> TriggerService: Filter + threshold + debounce
TriggerService -> RuntimeService: ImpactEvent(eventId, ts, magnitude, confidence)
RuntimeService -> StorageService: CreateEventLock(eventId, ts, pre=15s, post=45s)
StorageService -> StorageService: Resolve intersecting segmentIds
StorageService -> StorageService: Increment lockRefCount per segment
StorageService -> RuntimeService: EventLockApplied(eventId, lockedSegmentIds)
RuntimeService -> TriggerService: AckEvent(eventId)
```

## 5. Overlapping Event Behavior

- Locks are reference-counted per segment.
- If multiple events include the same segment, `lockRefCount` increments for each event.
- Unlock/removal of one event decrements ref count only for segments bound to that event.
- Segment becomes overwrite-eligible only when `lockRefCount == 0` and it is older than current write cursor policy.

## 6. Ring Reclaim Sequence

```text
StorageService -> StorageService: Check free space against low-watermark
StorageService -> StorageService: Select oldest unlocked segment candidate
StorageService -> StorageService: Delete media file + remove index rows
StorageService -> StorageService: Append reclaim journal entry
StorageService -> RuntimeService: ReclaimReport(bytesFreed,segmentsDeleted)
```

If no unlocked candidate exists:

```text
StorageService -> RuntimeService: StorageFault(code=ERR_NO_UNLOCKED_SEGMENTS)
RuntimeService -> CaptureService: PauseCaptureOrSingleSegmentMode(policy)
RuntimeService -> RuntimeService: Raise persistent health alarm
```

## 7. Startup Recovery Sequence

```text
RuntimeService -> StorageService: Initialize(storageProfile)
StorageService -> StorageService: Journal replay
StorageService -> StorageService: If journal invalid, index rebuild scan
StorageService -> StorageService: Rebuild event->segment lock map
StorageService -> RuntimeService: StorageReady(recovered=true|false, faults=[])
RuntimeService -> CaptureService: StartCapture only after StorageReady
RuntimeService -> TriggerService: ArmTrigger only after CaptureReady
```

Ordering rule: capture is not started until storage lock state is authoritative, preventing accidental overwrite of evidence after reboot.

## 8. State Machine (Service-Level)

```text
[BOOT]
  -> init ok -> [READY]
  -> init fail -> [DEGRADED]

[READY]
  -> StartCapture -> [RECORDING]

[RECORDING]
  -> ImpactEvent -> [RECORDING_WITH_PENDING_LOCK]
  -> CameraFault -> [DEGRADED_NO_CAPTURE]
  -> StorageFault(ERR_NO_UNLOCKED_SEGMENTS) -> [PAUSED_STORAGE_PROTECTED]

[RECORDING_WITH_PENDING_LOCK]
  -> EventLockApplied -> [RECORDING]
  -> LockApplyFailed(retriable) -> [RECORDING] + alarm

[DEGRADED_NO_CAPTURE]
  -> capture recovered -> [RECORDING]

[PAUSED_STORAGE_PROTECTED]
  -> manual unlock or config reclaim -> [RECORDING]
```

## 9. Pipeline Guarantees

- Event-lock commands are idempotent by `eventId`.
- Storage journal append is write-ahead relative to in-memory index mutation.
- Runtime issues lock requests in event timestamp order when batched.
- Trigger events are accepted even during transient capture restart, to lock pre-impact segments already on disk.
