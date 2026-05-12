from tests.fixtures.dashcam_sim import BYTES_PER_GB, BYTES_PER_MB, build_runtime


def test_soak_under_storage_pressure_with_periodic_impacts_preserves_invariants():
    runtime = build_runtime(
        storage_profile_bytes=2 * BYTES_PER_GB,
        segment_size_bytes=20 * BYTES_PER_MB,
    )

    impact_segments = set(range(15, 500, 37))
    accepted = runtime.record_segments(500, impact_segment_ids=impact_segments)

    assert accepted >= 450
    assert runtime.storage.used_bytes() <= runtime.config.storage_profile_bytes

    retained_ids = [seg.segment_id for seg in runtime.storage.segments]
    assert retained_ids == sorted(retained_ids)

    locked_segments = [seg for seg in runtime.storage.segments if seg.locked]
    assert len(locked_segments) > 0
    assert all(seg.event_id is not None for seg in locked_segments)
    assert runtime.config.offline_only is True
