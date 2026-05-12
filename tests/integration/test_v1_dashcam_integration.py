"""Task #6 integration tests for the isolated v1 dashcam simulation harness."""

import unittest

from tests.fixtures.dashcam_sim import BYTES_PER_MB, BYTES_PER_TB, RuntimeService, build_runtime


class V1DashcamIntegrationTests(unittest.TestCase):
    def test_loop_recording_continuity_and_segment_rotation(self):
        runtime = build_runtime(storage_profile_bytes=6 * 100 * BYTES_PER_MB)

        accepted = runtime.record_segments(10)

        self.assertEqual(accepted, 10)
        retained_ids = [seg.segment_id for seg in runtime.storage.segments]
        self.assertEqual(retained_ids, [4, 5, 6, 7, 8, 9])

        for segment in runtime.storage.segments:
            self.assertEqual(segment.resolution, "1280x720")
            self.assertEqual(segment.fps, 30)
            self.assertEqual(segment.camera, "front")

    def test_gsensor_event_locks_incident_window_from_overwrite(self):
        runtime = build_runtime(storage_profile_bytes=5 * 100 * BYTES_PER_MB)

        runtime.record_segments(4, impact_segment_ids={2})
        runtime.record_segments(4)

        retained_ids = [seg.segment_id for seg in runtime.storage.segments]
        self.assertTrue({1, 2, 3}.issubset(set(retained_ids)))

        lock_map = {seg.segment_id: seg.locked for seg in runtime.storage.segments}
        self.assertTrue(lock_map[1])
        self.assertTrue(lock_map[2])
        self.assertTrue(lock_map[3])

    def test_near_full_storage_keeps_locked_clips_and_rejects_unprotected_new_segments(self):
        runtime = build_runtime(storage_profile_bytes=3 * 100 * BYTES_PER_MB)

        runtime.record_segments(3, impact_segment_ids={1})
        before_ids = [seg.segment_id for seg in runtime.storage.segments]

        accepted = runtime.record_segments(2)
        after_ids = [seg.segment_id for seg in runtime.storage.segments]

        self.assertEqual(accepted, 0)
        self.assertEqual(before_ids, [0, 1, 2])
        self.assertEqual(after_ids, [0, 1, 2])
        self.assertTrue(all(seg.locked for seg in runtime.storage.segments))

    def test_recovery_after_abrupt_power_interruption_recovers_and_continues_recording(self):
        runtime = build_runtime(storage_profile_bytes=8 * 100 * BYTES_PER_MB)
        runtime.record_segments(3)
        runtime.start_uncommitted_segment()
        runtime.shutdown(clean=False)

        recovered = RuntimeService(runtime.config, runtime.state)
        recovered.boot()

        self.assertTrue(recovered.recovered_unclean_shutdown)
        self.assertEqual([seg.segment_id for seg in recovered.storage.segments], [0, 1, 2])

        accepted = recovered.record_segments(2)
        self.assertEqual(accepted, 2)
        self.assertEqual([seg.segment_id for seg in recovered.storage.segments], [0, 1, 2, 4, 5])

    def test_recovery_preserves_pending_post_event_lock(self):
        runtime = build_runtime(storage_profile_bytes=8 * 100 * BYTES_PER_MB)
        runtime.record_segments(3, impact_segment_ids={2})
        runtime.shutdown(clean=False)

        recovered = RuntimeService(runtime.config, runtime.state)
        recovered.boot()
        recovered.record_segments(1)

        lock_map = {seg.segment_id: seg.locked for seg in recovered.storage.segments}
        self.assertTrue(lock_map[3])

    def test_default_profile_is_1tb_offline_single_camera_baseline(self):
        runtime = build_runtime()

        self.assertEqual(runtime.config.storage_profile_bytes, BYTES_PER_TB)
        self.assertTrue(runtime.config.offline_only)
        self.assertTrue(runtime.config.single_front_camera)

        accepted = runtime.record_segments(12)
        self.assertEqual(accepted, 12)
        self.assertEqual(runtime.storage.used_bytes(), 12 * 100 * BYTES_PER_MB)


if __name__ == "__main__":
    unittest.main()
