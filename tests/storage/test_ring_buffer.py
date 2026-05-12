from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pkg.storage import RingBufferStorage, StorageFullError, resolve_retention_profile


def utc_timestamp(offset_seconds: int) -> datetime:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return base + timedelta(seconds=offset_seconds)


def create_segment_file(path: Path, size: int) -> None:
    path.write_bytes(b"a" * size)


class TestRingBufferStorage(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "storage"
        profile = resolve_retention_profile(
            profile_name="test-profile",
            configured_capacity_bytes=100,
            installed_capacity_bytes=100,
        )
        self.storage = RingBufferStorage(root_dir=str(self.root), profile=profile)

    def test_deterministic_oldest_unlocked_overwrite(self) -> None:
        source1 = Path(self.tmp.name) / "source1.mp4"
        source2 = Path(self.tmp.name) / "source2.mp4"
        source3 = Path(self.tmp.name) / "source3.mp4"
        source4 = Path(self.tmp.name) / "source4.mp4"
        create_segment_file(source1, 40)
        create_segment_file(source2, 40)
        create_segment_file(source3, 40)
        create_segment_file(source4, 40)

        self.storage.ingest_segment(source1, utc_timestamp(0), utc_timestamp(10))
        self.storage.ingest_segment(source2, utc_timestamp(11), utc_timestamp(20))
        self.storage.ingest_segment(source3, utc_timestamp(21), utc_timestamp(30))
        segments_after_three = self.storage.list_segments()
        self.assertEqual([s.sequence for s in segments_after_three], [2, 3])

        self.storage.ingest_segment(source4, utc_timestamp(31), utc_timestamp(40))
        segments = self.storage.list_segments()
        self.assertEqual([s.sequence for s in segments], [3, 4])
        self.assertEqual(self.storage.used_bytes(), 80)

    def test_event_locked_segments_are_not_overwritten(self) -> None:
        source1 = Path(self.tmp.name) / "lock1.mp4"
        source2 = Path(self.tmp.name) / "lock2.mp4"
        source3 = Path(self.tmp.name) / "lock3.mp4"
        create_segment_file(source1, 40)
        create_segment_file(source2, 40)
        create_segment_file(source3, 40)

        seg1 = self.storage.ingest_segment(source1, utc_timestamp(0), utc_timestamp(10))
        self.storage.ingest_segment(source2, utc_timestamp(11), utc_timestamp(20))
        self.storage.lock_event_window(
            event_id="event-1",
            window_start=utc_timestamp(0),
            window_end=utc_timestamp(20),
        )

        with self.assertRaises(StorageFullError):
            self.storage.ingest_segment(source3, utc_timestamp(21), utc_timestamp(30))

        segment_ids = [segment.segment_id for segment in self.storage.list_segments()]
        self.assertIn(seg1.segment_id, segment_ids)

    def test_retention_profile_scales_down_from_1tb(self) -> None:
        one_tib = 1024 * 1024 * 1024 * 1024
        profile = resolve_retention_profile(
            profile_name="default-1tb",
            configured_capacity_bytes=one_tib,
            installed_capacity_bytes=50 * 1024 * 1024 * 1024,
        )
        self.assertEqual(profile.max_supported_bytes, one_tib)
        self.assertEqual(profile.capacity_limit_bytes, 50 * 1024 * 1024 * 1024)

    def test_recovery_with_corrupted_catalog_uses_sidecars(self) -> None:
        source = Path(self.tmp.name) / "recovery.mp4"
        create_segment_file(source, 30)
        record = self.storage.ingest_segment(source, utc_timestamp(0), utc_timestamp(10))

        catalog_path = self.root / "catalog.json"
        catalog_path.write_text("{invalid-json", encoding="utf-8")

        profile = resolve_retention_profile(
            profile_name="test-profile",
            configured_capacity_bytes=100,
            installed_capacity_bytes=100,
        )
        recovered = RingBufferStorage(root_dir=str(self.root), profile=profile)
        segments = recovered.list_segments()
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].segment_id, record.segment_id)
        self.assertTrue(catalog_path.exists())
        self.assertTrue(json.loads(catalog_path.read_text(encoding="utf-8")))

    def test_release_event_lock_allows_overwrite(self) -> None:
        source1 = Path(self.tmp.name) / "release1.mp4"
        source2 = Path(self.tmp.name) / "release2.mp4"
        source3 = Path(self.tmp.name) / "release3.mp4"
        create_segment_file(source1, 40)
        create_segment_file(source2, 40)
        create_segment_file(source3, 40)

        self.storage.ingest_segment(source1, utc_timestamp(0), utc_timestamp(10), event_id="event-1")
        self.storage.ingest_segment(source2, utc_timestamp(11), utc_timestamp(20), event_id="event-1")

        with self.assertRaises(StorageFullError):
            self.storage.ingest_segment(source3, utc_timestamp(21), utc_timestamp(30))

        released = self.storage.release_event_lock("event-1")
        self.assertEqual(released, 2)

        self.storage.ingest_segment(source3, utc_timestamp(21), utc_timestamp(30))
        self.assertEqual(len(self.storage.list_segments()), 2)


if __name__ == "__main__":
    unittest.main()
