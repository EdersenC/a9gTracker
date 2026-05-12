from __future__ import annotations

import json
import os
from pathlib import Path

from .models import SegmentRecord


class StorageIndex:
    def __init__(self, root_dir: str) -> None:
        self.root = Path(root_dir)
        self.media_dir = self.root / "media"
        self.meta_dir = self.root / "metadata"
        self.catalog_path = self.root / "catalog.json"
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self.meta_dir.mkdir(parents=True, exist_ok=True)
        self.root.mkdir(parents=True, exist_ok=True)

        self._segments: list[SegmentRecord] = []
        self._next_sequence = 1

    def load(self) -> None:
        recovered = False
        if self.catalog_path.exists():
            try:
                payload = json.loads(self.catalog_path.read_text(encoding="utf-8"))
                self._segments = [
                    SegmentRecord.from_dict(item)
                    for item in payload.get("segments", [])
                ]
                self._next_sequence = int(payload.get("next_sequence", 1))
            except (json.JSONDecodeError, OSError, ValueError, TypeError):
                recovered = True
                self._segments = self._load_from_sidecars()
        else:
            self._segments = self._load_from_sidecars()

        self._reconcile_with_filesystem()
        self._segments.sort(key=lambda segment: (segment.sequence, segment.segment_id))
        self._next_sequence = max(
            self._next_sequence, max((segment.sequence for segment in self._segments), default=0) + 1
        )

        if recovered or not self.catalog_path.exists():
            self.persist()

    def list_segments(self) -> list[SegmentRecord]:
        return list(self._segments)

    def next_sequence(self) -> int:
        sequence = self._next_sequence
        self._next_sequence += 1
        return sequence

    def add_segment(self, segment: SegmentRecord) -> None:
        self._segments.append(segment)
        self._segments.sort(key=lambda item: (item.sequence, item.segment_id))
        self._write_sidecar(segment)

    def remove_segment(self, segment_id: str) -> SegmentRecord | None:
        for index, segment in enumerate(self._segments):
            if segment.segment_id == segment_id:
                removed = self._segments.pop(index)
                self._delete_sidecar(removed.segment_id)
                return removed
        return None

    def update_segment(self, segment: SegmentRecord) -> None:
        for index, existing in enumerate(self._segments):
            if existing.segment_id == segment.segment_id:
                self._segments[index] = segment
                self._write_sidecar(segment)
                return
        self.add_segment(segment)

    def persist(self) -> None:
        payload = {
            "next_sequence": self._next_sequence,
            "segments": [segment.to_dict() for segment in self._segments],
        }
        self._atomic_write_json(self.catalog_path, payload)

    def _reconcile_with_filesystem(self) -> None:
        available_records: list[SegmentRecord] = []
        known_ids = set()
        referenced_files: set[Path] = set()
        for segment in self._segments:
            media_path = Path(segment.file_path)
            if media_path.exists():
                segment.size_bytes = media_path.stat().st_size
                available_records.append(segment)
                known_ids.add(segment.segment_id)
                referenced_files.add(media_path.resolve())

        for sidecar_record in self._load_from_sidecars():
            if sidecar_record.segment_id in known_ids:
                continue
            media_path = Path(sidecar_record.file_path)
            if media_path.exists():
                sidecar_record.size_bytes = media_path.stat().st_size
                available_records.append(sidecar_record)
                referenced_files.add(media_path.resolve())

        for media_file in self.media_dir.iterdir():
            if not media_file.is_file():
                continue
            if media_file.resolve() in referenced_files:
                continue
            try:
                media_file.unlink()
            except OSError:
                continue
        self._segments = available_records

    def _load_from_sidecars(self) -> list[SegmentRecord]:
        segments: list[SegmentRecord] = []
        for file_path in sorted(self.meta_dir.glob("*.json")):
            try:
                payload = json.loads(file_path.read_text(encoding="utf-8"))
                segments.append(SegmentRecord.from_dict(payload))
            except (json.JSONDecodeError, OSError, ValueError, TypeError):
                continue
        return segments

    def _sidecar_path(self, segment_id: str) -> Path:
        return self.meta_dir / f"{segment_id}.json"

    def _write_sidecar(self, segment: SegmentRecord) -> None:
        self._atomic_write_json(self._sidecar_path(segment.segment_id), segment.to_dict())

    def _delete_sidecar(self, segment_id: str) -> None:
        sidecar = self._sidecar_path(segment_id)
        try:
            sidecar.unlink()
        except FileNotFoundError:
            return

    def _atomic_write_json(self, path: Path, payload: dict) -> None:
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        os.replace(tmp_path, path)
