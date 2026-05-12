from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

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
        config_data = _load_config(Path(config_path))
        storage_cfg = _as_mapping(config_data.get("storage"), "storage")
        lock_cfg = _as_mapping(storage_cfg.get("lock"), "storage.lock")
        ring_buffer_cfg = _as_mapping(storage_cfg.get("ring_buffer"), "storage.ring_buffer")

        lock_policy = str(lock_cfg.get("policy", "event-protected"))
        if lock_policy != "event-protected":
            raise ValueError(
                f"unsupported lock policy {lock_policy!r}; expected 'event-protected'"
            )

        profile = resolve_retention_profile(
            profile_name=str(storage_cfg.get("profile", "user-profile")),
            configured_capacity_bytes=_to_int(
                storage_cfg.get("capacity_limit_bytes", 0),
                "storage.capacity_limit_bytes",
            ),
            installed_capacity_bytes=installed_capacity_bytes,
            min_free_reserve_bytes=_to_int(
                storage_cfg.get("min_free_reserve_bytes", 0),
                "storage.min_free_reserve_bytes",
            ),
            lock_default_ttl_seconds=_to_int(
                lock_cfg.get("default_ttl_seconds", 0),
                "storage.lock.default_ttl_seconds",
            ),
            max_supported_bytes=_to_int(
                storage_cfg.get("max_supported_bytes", 0),
                "storage.max_supported_bytes",
            ),
            overwrite_policy=str(
                ring_buffer_cfg.get("overwrite_policy", "oldest-unlocked-first")
            ),
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


def _to_int(value: Any, field_name: str) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer, got boolean")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc


def _as_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a mapping")
    return value


def _load_config(config_path: Path) -> dict[str, Any]:
    raw = config_path.read_text(encoding="utf-8")
    if config_path.suffix.lower() == ".json":
        payload = json.loads(raw) or {}
    else:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = _parse_simple_yaml(raw)
    if not isinstance(payload, dict):
        raise ValueError("configuration root must be a mapping")
    return payload


def _parse_simple_yaml(raw: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip(" "))
        if "\t" in line[:indent]:
            raise ValueError("tabs are not supported in configuration indentation")
        content = line[indent:]
        if ":" not in content:
            raise ValueError(f"invalid configuration line: {line!r}")
        key, value = content.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"invalid configuration key in line: {line!r}")

        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            raise ValueError(f"invalid indentation in line: {line!r}")
        parent = stack[-1][1]
        if value == "":
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
            continue
        parent[key] = _parse_scalar(value)
    return root


def _parse_scalar(value: str) -> Any:
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value
