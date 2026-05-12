from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from .index import StorageIndex
from .models import RetentionProfile, SegmentRecord, utc_now


class StorageFullError(RuntimeError):
    pass


class RingBufferStorage:
    def __init__(self, root_dir: str, profile: RetentionProfile) -> None:
        self.profile = profile
        self.index = StorageIndex(root_dir)
        self.index.load()

    @property
    def capacity_limit_bytes(self) -> int:
        adjusted = self.profile.capacity_limit_bytes - self.profile.min_free_reserve_bytes
        return max(0, adjusted)

    def used_bytes(self) -> int:
        return sum(segment.size_bytes for segment in self.index.list_segments())

    def free_bytes(self) -> int:
        return max(0, self.capacity_limit_bytes - self.used_bytes())

    def list_segments(self) -> list[SegmentRecord]:
        return self.index.list_segments()

    def ingest_segment(
        self,
        source_path: str,
        started_at: datetime,
        ended_at: datetime,
        event_id: str | None = None,
        lock_until: datetime | None = None,
    ) -> SegmentRecord:
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"segment source missing: {source}")

        segment_size = source.stat().st_size
        self._evict_until_fit(segment_size, utc_now())

        sequence = self.index.next_sequence()
        extension = source.suffix or ".mp4"
        segment_id = f"seg-{sequence:010d}-{uuid.uuid4().hex[:8]}"
        destination = self.index.media_dir / f"{segment_id}{extension}"
        shutil.copy2(source, destination)

        record = SegmentRecord(
            segment_id=segment_id,
            sequence=sequence,
            file_name=destination.name,
            file_path=str(destination),
            size_bytes=destination.stat().st_size,
            started_at=started_at,
            ended_at=ended_at,
            locked=event_id is not None,
            lock_reason="event" if event_id else None,
            lock_until=lock_until or self._default_lock_until(),
            event_id=event_id,
        )
        self.index.add_segment(record)
        self.index.persist()
        return record

    def lock_event_window(
        self,
        event_id: str,
        window_start: datetime,
        window_end: datetime,
        lock_until: datetime | None = None,
    ) -> int:
        locked = 0
        for segment in self.index.list_segments():
            overlaps = segment.started_at <= window_end and segment.ended_at >= window_start
            if not overlaps:
                continue
            segment.locked = True
            segment.lock_reason = "event"
            segment.event_id = event_id
            segment.lock_until = lock_until or self._default_lock_until()
            self.index.update_segment(segment)
            locked += 1
        self.index.persist()
        return locked

    def release_event_lock(self, event_id: str) -> int:
        released = 0
        for segment in self.index.list_segments():
            if segment.event_id != event_id:
                continue
            segment.locked = False
            segment.lock_reason = None
            segment.lock_until = None
            segment.event_id = None
            self.index.update_segment(segment)
            released += 1
        self.index.persist()
        return released

    def enforce_capacity(self) -> None:
        self._evict_until_fit(required_bytes=0, now=utc_now())
        self.index.persist()

    def _default_lock_until(self) -> datetime | None:
        ttl = self.profile.lock_default_ttl_seconds
        if ttl <= 0:
            return None
        return utc_now() + timedelta(seconds=ttl)

    def _evict_until_fit(self, required_bytes: int, now: datetime) -> None:
        if required_bytes > self.capacity_limit_bytes:
            raise StorageFullError(
                f"segment size {required_bytes} exceeds capacity limit {self.capacity_limit_bytes}"
            )

        bytes_to_free = (self.used_bytes() + required_bytes) - self.capacity_limit_bytes
        if bytes_to_free <= 0:
            return

        candidates = [
            segment
            for segment in self.index.list_segments()
            if not segment.is_lock_active(now)
        ]
        candidates.sort(key=lambda segment: (segment.sequence, segment.segment_id))

        reclaimed = 0
        for candidate in candidates:
            if reclaimed >= bytes_to_free:
                break
            reclaimed += candidate.size_bytes
            self._delete_segment(candidate)

        if reclaimed < bytes_to_free:
            raise StorageFullError(
                "insufficient unlocked segments to reclaim required storage"
            )

    def _delete_segment(self, segment: SegmentRecord) -> None:
        try:
            Path(segment.file_path).unlink()
        except FileNotFoundError:
            pass
        self.index.remove_segment(segment.segment_id)
