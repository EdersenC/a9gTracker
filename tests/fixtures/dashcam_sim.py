"""Deterministic task-scoped v1 dashcam simulation for integration validation.

This fixture models the v1 architecture contracts at a system level:
- capture service: emits fixed 720p/30fps front-camera segments
- storage service: ring-buffer rotation with event lock protection
- trigger service: G-sensor impact detection and event creation
- runtime service: boot/recovery behavior and offline-only policy
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional


BYTES_PER_GB = 1_000_000_000
BYTES_PER_TB = 1_000_000_000_000
BYTES_PER_MB = 1_000_000


@dataclass
class DashcamConfig:
    resolution: str = "1280x720"
    fps: int = 30
    segment_seconds: int = 60
    single_front_camera: bool = True
    offline_only: bool = True
    storage_profile_bytes: int = BYTES_PER_TB
    segment_size_bytes: int = 100 * BYTES_PER_MB


@dataclass
class Segment:
    segment_id: int
    start_second: int
    duration_seconds: int
    resolution: str
    fps: int
    camera: str = "front"
    size_bytes: int = 0
    locked: bool = False
    event_id: Optional[int] = None


@dataclass
class Event:
    event_id: int
    impact_g: float
    impact_second: int
    incident_segment_id: int


@dataclass
class StateStore:
    """Persisted metadata that survives runtime restarts."""

    segments: List[Segment] = field(default_factory=list)
    next_segment_id: int = 0
    next_event_id: int = 1
    unclean_shutdown: bool = False
    pending_post_lock_segments: Dict[int, List[int]] = field(default_factory=dict)


class CaptureService:
    def __init__(self, config: DashcamConfig, state: StateStore):
        self.config = config
        self.state = state

    def build_segment(self) -> Segment:
        segment_id = self.state.next_segment_id
        start_second = segment_id * self.config.segment_seconds
        self.state.next_segment_id += 1
        return Segment(
            segment_id=segment_id,
            start_second=start_second,
            duration_seconds=self.config.segment_seconds,
            resolution=self.config.resolution,
            fps=self.config.fps,
            size_bytes=self.config.segment_size_bytes,
        )


class StorageService:
    def __init__(self, config: DashcamConfig, state: StateStore):
        self.config = config
        self.state = state
        self.segments = state.segments

    def used_bytes(self) -> int:
        return sum(seg.size_bytes for seg in self.segments)

    def _evict_until_fit(self, incoming_size: int) -> bool:
        while self.used_bytes() + incoming_size > self.config.storage_profile_bytes:
            removable = next((seg for seg in self.segments if not seg.locked), None)
            if removable is None:
                return False
            self.segments.remove(removable)
        return True

    def ingest(self, segment: Segment) -> bool:
        if not self._evict_until_fit(segment.size_bytes):
            return False
        self.segments.append(segment)
        self.segments.sort(key=lambda s: s.segment_id)
        return True

    def by_id(self, segment_id: int) -> Optional[Segment]:
        return next((seg for seg in self.segments if seg.segment_id == segment_id), None)

    def lock_segment(self, segment_id: int, event_id: int) -> None:
        segment = self.by_id(segment_id)
        if segment:
            segment.locked = True
            segment.event_id = event_id


class TriggerService:
    def __init__(self, state: StateStore, threshold_g: float = 2.5):
        self.state = state
        self.threshold_g = threshold_g

    def detect(self, impact_g: float, impact_second: int, incident_segment_id: int) -> Optional[Event]:
        if impact_g < self.threshold_g:
            return None
        event = Event(
            event_id=self.state.next_event_id,
            impact_g=impact_g,
            impact_second=impact_second,
            incident_segment_id=incident_segment_id,
        )
        self.state.next_event_id += 1
        return event


class RuntimeService:
    def __init__(self, config: DashcamConfig, state: Optional[StateStore] = None):
        self.config = config
        self.state = state or StateStore()
        self.capture = CaptureService(config, self.state)
        self.storage = StorageService(config, self.state)
        self.trigger = TriggerService(self.state)
        self.recovered_unclean_shutdown = False
        self._volatile_open_segment: Optional[Segment] = None
        self._pending_post_lock_segments = self.state.pending_post_lock_segments
        self.events: List[Event] = []

    def boot(self) -> None:
        if self.state.unclean_shutdown:
            self.recovered_unclean_shutdown = True
            self.state.unclean_shutdown = False

    def shutdown(self, clean: bool = True) -> None:
        self.state.unclean_shutdown = not clean
        self._volatile_open_segment = None

    def start_uncommitted_segment(self) -> None:
        self._volatile_open_segment = self.capture.build_segment()

    def _apply_pending_post_locks(self, segment_id: int) -> None:
        event_ids = self._pending_post_lock_segments.pop(segment_id, [])
        for event_id in event_ids:
            self.storage.lock_segment(segment_id, event_id)

    def _record_impact(self, segment: Segment, impact_g: float = 3.8) -> Optional[Event]:
        impact_second = segment.start_second + (segment.duration_seconds // 2)
        event = self.trigger.detect(impact_g, impact_second, segment.segment_id)
        if not event:
            return None

        self.events.append(event)
        self.storage.lock_segment(segment.segment_id, event.event_id)
        self.storage.lock_segment(segment.segment_id - 1, event.event_id)
        target_post_segment = segment.segment_id + 1
        pending_event_ids = self._pending_post_lock_segments.setdefault(target_post_segment, [])
        if event.event_id not in pending_event_ids:
            pending_event_ids.append(event.event_id)
        return event

    def record_segments(self, count: int, impact_segment_ids: Optional[Iterable[int]] = None) -> int:
        impact_ids = set(impact_segment_ids or [])
        accepted = 0
        for _ in range(count):
            segment = self.capture.build_segment()
            stored = self.storage.ingest(segment)
            if not stored:
                continue
            accepted += 1
            self._apply_pending_post_locks(segment.segment_id)
            if segment.segment_id in impact_ids:
                self._record_impact(segment)
        return accepted

    def summary(self) -> Dict[str, int]:
        locked = [seg for seg in self.storage.segments if seg.locked]
        return {
            "segment_count": len(self.storage.segments),
            "locked_segment_count": len(locked),
            "used_bytes": self.storage.used_bytes(),
            "event_count": len(self.events),
        }


def build_runtime(
    *,
    storage_profile_bytes: int = BYTES_PER_TB,
    segment_size_bytes: int = 100 * BYTES_PER_MB,
) -> RuntimeService:
    config = DashcamConfig(
        storage_profile_bytes=storage_profile_bytes,
        segment_size_bytes=segment_size_bytes,
    )
    runtime = RuntimeService(config)
    runtime.boot()
    return runtime
