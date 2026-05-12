from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml

from pkg.storage import RingBufferStorage, resolve_retention_profile


class StorageService:
    def __init__(self, storage: RingBufferStorage) -> None:
        self.storage = storage

    @classmethod
    def from_config(
        cls,
        config_path: str,
        storage_root: str,
        installed_capacity_bytes: int,
    ) -> "StorageService":
        config_data = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
        storage_cfg = config_data.get("storage", {})
        lock_cfg = storage_cfg.get("lock", {})

        profile = resolve_retention_profile(
            profile_name=str(storage_cfg.get("profile", "user-profile")),
            configured_capacity_bytes=int(storage_cfg.get("capacity_limit_bytes", 0)),
            installed_capacity_bytes=installed_capacity_bytes,
            min_free_reserve_bytes=int(storage_cfg.get("min_free_reserve_bytes", 0)),
            lock_default_ttl_seconds=int(lock_cfg.get("default_ttl_seconds", 0)),
        )

        return cls(storage=RingBufferStorage(root_dir=storage_root, profile=profile))

    def store_segment(
        self,
        source_path: str,
        started_at: datetime,
        ended_at: datetime,
        event_id: str | None = None,
    ) -> dict:
        record = self.storage.ingest_segment(
            source_path=source_path,
            started_at=started_at,
            ended_at=ended_at,
            event_id=event_id,
        )
        return record.to_dict()

    def lock_event_window(
        self,
        event_id: str,
        window_start: datetime,
        window_end: datetime,
    ) -> int:
        return self.storage.lock_event_window(
            event_id=event_id,
            window_start=window_start,
            window_end=window_end,
        )

    def release_event_lock(self, event_id: str) -> int:
        return self.storage.release_event_lock(event_id)

    def list_segments(self) -> list[dict]:
        return [segment.to_dict() for segment in self.storage.list_segments()]
