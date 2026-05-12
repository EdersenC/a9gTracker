from tests.fixtures.dashcam_sim import BYTES_PER_MB, BYTES_PER_TB, RuntimeService, StateStore, build_runtime


def test_loop_recording_continuity_and_segment_rotation():
    runtime = build_runtime(storage_profile_bytes=6 * 100 * BYTES_PER_MB)

    accepted = runtime.record_segments(10)

    assert accepted == 10
    retained_ids = [seg.segment_id for seg in runtime.storage.segments]
    assert retained_ids == [4, 5, 6, 7, 8, 9]

    for segment in runtime.storage.segments:
        assert segment.resolution == "1280x720"
        assert segment.fps == 30
        assert segment.camera == "front"


def test_gsensor_event_locks_incident_window_from_overwrite():
    runtime = build_runtime(storage_profile_bytes=5 * 100 * BYTES_PER_MB)

    runtime.record_segments(4, impact_segment_ids={2})
    runtime.record_segments(4)

    retained_ids = [seg.segment_id for seg in runtime.storage.segments]
    assert {1, 2, 3}.issubset(set(retained_ids))

    lock_map = {seg.segment_id: seg.locked for seg in runtime.storage.segments}
    assert lock_map[1] is True
    assert lock_map[2] is True
    assert lock_map[3] is True


def test_near_full_storage_keeps_locked_clips_and_rejects_unprotected_new_segments():
    runtime = build_runtime(storage_profile_bytes=3 * 100 * BYTES_PER_MB)

    runtime.record_segments(3, impact_segment_ids={1})
    before_ids = [seg.segment_id for seg in runtime.storage.segments]

    accepted = runtime.record_segments(2)
    after_ids = [seg.segment_id for seg in runtime.storage.segments]

    assert accepted == 0
    assert before_ids == [0, 1, 2]
    assert after_ids == [0, 1, 2]
    assert all(seg.locked for seg in runtime.storage.segments)


def test_recovery_after_abrupt_power_interruption_recovers_and_continues_recording():
    runtime = build_runtime(storage_profile_bytes=8 * 100 * BYTES_PER_MB)
    runtime.record_segments(3)
    runtime.start_uncommitted_segment()
    runtime.shutdown(clean=False)

    recovered = RuntimeService(runtime.config, runtime.state)
    recovered.boot()

    assert recovered.recovered_unclean_shutdown is True
    assert [seg.segment_id for seg in recovered.storage.segments] == [0, 1, 2]

    accepted = recovered.record_segments(2)
    assert accepted == 2
    assert [seg.segment_id for seg in recovered.storage.segments] == [0, 1, 2, 4, 5]


def test_default_profile_is_1tb_offline_single_camera_baseline():
    runtime = build_runtime()

    assert runtime.config.storage_profile_bytes == BYTES_PER_TB
    assert runtime.config.offline_only is True
    assert runtime.config.single_front_camera is True

    accepted = runtime.record_segments(12)
    assert accepted == 12
    assert runtime.storage.used_bytes() == 12 * 100 * BYTES_PER_MB
