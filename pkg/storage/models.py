from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_utc(value: str | None) -> datetime | None:
    if value is None or value == "":
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def to_iso8601(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime values must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class RetentionProfile:
    name: str
    max_supported_bytes: int
    capacity_limit_bytes: int
    min_free_reserve_bytes: int = 0
    lock_default_ttl_seconds: int = 0
    overwrite_policy: str = "oldest-unlocked-first"


@dataclass
class SegmentRecord:
    segment_id: str
    sequence: int
    file_name: str
    file_path: str
    size_bytes: int
    started_at: datetime
    ended_at: datetime
    created_at: datetime = field(default_factory=utc_now)
    locked: bool = False
    lock_reason: str | None = None
    lock_until: datetime | None = None
    event_id: str | None = None

    def is_lock_active(self, now: datetime | None = None) -> bool:
        if not self.locked:
            return False
        if self.lock_until is None:
            return True
        current = now or utc_now()
        return current < self.lock_until

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "sequence": self.sequence,
            "file_name": self.file_name,
            "file_path": self.file_path,
            "size_bytes": self.size_bytes,
            "started_at": to_iso8601(self.started_at),
            "ended_at": to_iso8601(self.ended_at),
            "created_at": to_iso8601(self.created_at),
            "locked": self.locked,
            "lock_reason": self.lock_reason,
            "lock_until": to_iso8601(self.lock_until),
            "event_id": self.event_id,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SegmentRecord":
        return cls(
            segment_id=str(payload["segment_id"]),
            sequence=int(payload["sequence"]),
            file_name=str(payload["file_name"]),
            file_path=str(payload["file_path"]),
            size_bytes=int(payload["size_bytes"]),
            started_at=parse_utc(payload["started_at"]) or utc_now(),
            ended_at=parse_utc(payload["ended_at"]) or utc_now(),
            created_at=parse_utc(payload.get("created_at")) or utc_now(),
            locked=bool(payload.get("locked", False)),
            lock_reason=payload.get("lock_reason"),
            lock_until=parse_utc(payload.get("lock_until")),
            event_id=payload.get("event_id"),
        )
