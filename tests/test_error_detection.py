import unittest

import error_detection as ed


class TestErrorDetection(unittest.TestCase):
    def test_detector_records_error(self):
        detector = ed.ErrorDetector()
        detector.error(ed.ErrorCode.IO_FAILURE, "write failed", {"file": "x"})
        self.assertTrue(detector.has_errors())
        self.assertEqual(detector.events[0]["code"], ed.ErrorCode.IO_FAILURE)

    def test_validate_settings_success(self):
        settings = {
            "provider": "hologram",
            "server": {
                "host": "example.com",
                "port": 443,
                "auth": "abc",
                "routes": {"location": "/l", "update": "/u"},
            },
            "modes": {"currentMode": "tracking", "tracking": {"interval": 1}},
        }
        self.assertTrue(ed.validate_settings(settings))

    def test_validate_settings_missing_key(self):
        with self.assertRaises(ed.DetectedError) as ctx:
            ed.validate_settings({"provider": "hologram"})
        self.assertEqual(ctx.exception.code, ed.ErrorCode.SETTINGS_INVALID)

    def test_validate_network_snapshot(self):
        snapshot = {
            "scan": [],
            "imei": "x",
            "iccid": "y",
            "quaility": 10,
            "registered": True,
            "status": "ok",
        }
        self.assertTrue(ed.validate_network_snapshot(snapshot))

    def test_validate_instruction_rejects_unknown_action(self):
        with self.assertRaises(ed.DetectedError) as ctx:
            ed.validate_instruction({"action": "boom"})
        self.assertEqual(ctx.exception.code, ed.ErrorCode.INSTRUCTION_INVALID)

    def test_validate_instruction_update_requires_data(self):
        with self.assertRaises(ed.DetectedError) as ctx:
            ed.validate_instruction({"action": "update"})
        self.assertEqual(ctx.exception.code, ed.ErrorCode.INSTRUCTION_INVALID)
        self.assertEqual(ctx.exception.message, "Update instruction missing data")
        self.assertEqual(ctx.exception.context, {})

        update_instruction = {
            "action": "update",
            "data": {"url": "https://example.com/fw.bin"},
        }
        self.assertTrue(ed.validate_instruction(update_instruction))

    def test_validate_chunk_state_rejects_invalid_range(self):
        with self.assertRaises(ed.DetectedError) as ctx:
            ed.validate_chunk_state(10, 11, "x")
        self.assertEqual(ctx.exception.code, ed.ErrorCode.CHUNK_INVALID)


if __name__ == "__main__":
    unittest.main()
