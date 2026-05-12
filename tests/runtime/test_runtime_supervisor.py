import os
import tempfile
import textwrap
import threading
import time
import unittest
from pathlib import Path

from services.runtime.runtime_config import RuntimeConfig, ServiceSpec
from services.runtime.runtime_supervisor import RuntimeSupervisor


class RuntimeSupervisorTests(unittest.TestCase):
    def test_supervisor_starts_and_stops_services(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_dir = root / "state"
            log_dir = root / "logs"

            service_script = root / "service.sh"
            service_script.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env bash
                    set -euo pipefail
                    trap 'exit 0' TERM INT
                    while true; do
                      sleep 1
                    done
                    """
                ),
                encoding="utf-8",
            )
            os.chmod(service_script, 0o755)

            cfg = RuntimeConfig(
                device_id="test",
                runtime_state_dir=state_dir,
                log_dir=log_dir,
                poll_interval_seconds=0.2,
                startup_grace_seconds=1,
                shutdown_grace_seconds=1,
                services=[
                    ServiceSpec(
                        name="storage",
                        command=[str(service_script)],
                        start_after=[],
                        restart="always",
                        stop_timeout_seconds=2,
                        healthcheck=None,
                        pre_stop=None,
                    ),
                    ServiceSpec(
                        name="capture",
                        command=[str(service_script)],
                        start_after=["storage"],
                        restart="always",
                        stop_timeout_seconds=2,
                        healthcheck=None,
                        pre_stop=None,
                    ),
                ],
            )

            supervisor = RuntimeSupervisor(cfg, install_signal_handlers=False)
            thread = threading.Thread(target=supervisor.run_forever, daemon=True)
            thread.start()

            time.sleep(0.8)
            self.assertTrue((state_dir / "runtime-state.json").exists())
            health = supervisor.snapshot_health()
            self.assertIn("storage", health["services"])
            self.assertIn("capture", health["services"])

            supervisor._stopping = True
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
