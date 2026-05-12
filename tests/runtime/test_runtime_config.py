import tempfile
import unittest
from pathlib import Path

from services.runtime.runtime_config import load_runtime_config


class RuntimeConfigTests(unittest.TestCase):
    def test_load_config(self) -> None:
        data = """
runtime:
  device_id: unit-test
  runtime_state_dir: /tmp/runtime-state
  log_dir: /tmp/runtime-log
services:
  - name: storage
    command: ["/bin/echo", "ok"]
    start_after: []
    restart: always
    stop_timeout_seconds: 5
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runtime.yaml"
            path.write_text(data, encoding="utf-8")
            cfg = load_runtime_config(path)

        self.assertEqual(cfg.device_id, "unit-test")
        self.assertEqual(len(cfg.services), 1)
        self.assertEqual(cfg.services[0].name, "storage")
        self.assertEqual(cfg.services[0].command, ["/bin/echo", "ok"])


if __name__ == "__main__":
    unittest.main()
