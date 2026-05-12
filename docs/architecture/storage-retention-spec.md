# Storage and Retention Specification (v1)

## 1. Purpose

Defines capacity planning, retention policy, event-lock preservation, and overwrite rules for loop recording up to 1TB installed media.

## 2. Capacity Inputs

- Installed capacity `C_gib` (GiB), where v1 supports `C_gib <= 1024`.
- Profile parameters (default values):
- `P_system = max(16 GiB, 0.03 * C_gib)`
- `P_safety = max(8 GiB, 0.02 * C_gib)`
- `P_metadata = max(4 GiB, 0.01 * C_gib)`

Derived:

- `U_gib = C_gib - (P_system + P_safety + P_metadata)` usable recording pool.
- `Q_lock = min(0.30 * U_gib, 300 GiB)` lock-protected quota.
- `Q_loop = U_gib - Q_lock` loop-overwrite quota.

Interpretation:

- `Q_loop` is continuously recyclable ring space.
- `Q_lock` is the budget for event-protected segments.

## 3. Default 1TB Profile (Validation Baseline)

Given `C_gib = 1024`:

- `P_system = 30.72 GiB`
- `P_safety = 20.48 GiB`
- `P_metadata = 10.24 GiB`
- `U_gib = 962.56 GiB`
- `Q_lock = 288.77 GiB`
- `Q_loop = 673.79 GiB`

## 4. Recording Rate Assumptions (720p/30)

Planning bitrate envelope for single front camera encoded video:

- Nominal: `4 Mbps` (about `1.8 GB/hour`).
- Stress/scene complexity: `6 Mbps` (about `2.7 GB/hour`).

Approximate loop retention window using `Q_loop`:

- At 4 Mbps with 1TB default profile: about `374 hours`.
- At 6 Mbps with 1TB default profile: about `249 hours`.

These are planning values; exact runtime retention varies by encoder output and scene entropy.

## 5. Segment Index Model

Each segment index row must include:

- `segmentId`
- `cameraId`
- `startMonoNs`, `endMonoNs`
- `bytes`
- `checksum`
- `createdAt`
- `lockRefCount` (integer >= 0)
- `eventIds[]` (or relation table)

Event table must include:

- `eventId`
- `triggerTsMonoNs`
- `preSec`, `postSec`
- `status` (`ACTIVE`, `CLEARED`, `EXPIRED`)
- `lockedSegmentCount`

## 6. Deterministic Overwrite Rules

Overwrite selection order:

1. Candidate pool is only segments with `lockRefCount == 0`.
2. Select oldest candidate by `startMonoNs` ascending.
3. Delete file, then remove index row, then journal reclaim record.

Hard constraints:

- Locked segments (`lockRefCount > 0`) are never auto-deleted.
- Reclaim must stop before violating `P_safety` free-space floor.
- If no unlocked segments remain and free space hits floor, system enters protected pause (`ERR_NO_UNLOCKED_SEGMENTS`).

## 7. Event-Lock Capacity Behavior

### Normal case

- New event lock succeeds if required segments fit inside remaining lock capacity budget.

### Budget pressure case

If locking the new event would exceed `Q_lock`:

1. Attempt to purge `CLEARED`/expired events and decrement their refs.
2. Recompute required lock bytes.
3. If still above `Q_lock`, reject with `ERR_LOCK_QUOTA_EXCEEDED` and raise runtime alarm.
4. Recording continues in loop area if `Q_loop` reclaimable space exists.

Rationale: v1 must not silently discard existing locked evidence.

## 8. Startup and Corruption Recovery Rules

- Journal-first recovery path is mandatory.
- If journal fails validation, perform media scan and reconstruct segment index.
- During reconstruction, all segments referenced by valid event records are conservatively treated as locked.
- Overwrite is disabled until reconstruction completes.

## 9. Power-Loss Behavior

- Segment files are written to temporary name and atomically renamed on close.
- Journal entries include CRC and monotonic sequence to detect torn writes.
- On reboot, incomplete temp segments are quarantined and excluded from lock matching unless checksum-valid and time-bounded.

## 10. User Configuration Constraints

User may tune:

- Segment duration.
- Trigger pre/post window.
- Retention profile percentages within safe bounds.

Validation guardrails:

- `C_gib <= 1024` for v1 support commitment.
- `Q_loop >= 24 hours` at nominal bitrate for accepted config.
- `P_safety >= 8 GiB` always.

## 11. Errors and Alarms

Required storage errors:

- `ERR_MEDIA_READ_ONLY`
- `ERR_INDEX_CORRUPT`
- `ERR_JOURNAL_CORRUPT`
- `ERR_LOCK_QUOTA_EXCEEDED`
- `ERR_NO_UNLOCKED_SEGMENTS`

Runtime alarm levels:

- `WARN`: reclaim lag, elevated bitrate.
- `ERROR`: lock quota exceeded, camera down.
- `CRITICAL`: index corruption unrecoverable, media unavailable.
