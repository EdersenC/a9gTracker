from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .runtime_config import RuntimeConfig, ServiceSpec


@dataclass
class ManagedProcess:
    spec: ServiceSpec
    process: subprocess.Popen[str]
    started_at: float
    log_handle: Any


class RuntimeSupervisor:
    def __init__(self, config: RuntimeConfig, install_signal_handlers: bool = True) -> None:
        self._config = config
        self._install_handlers = install_signal_handlers
        self._procs: dict[str, ManagedProcess] = {}
        self._stopping = False
        self._state_file = self._config.runtime_state_dir / "runtime-state.json"
        self._health: dict[str, dict[str, Any]] = {}

    def run_forever(self) -> None:
        self._prepare_paths()
        if self._install_handlers:
            self._install_signal_handlers()
        self._start_in_dependency_order()
        self._write_state({"status": "running", "pid": os.getpid()})

        while not self._stopping:
            self._poll_processes()
            self._write_state(self.snapshot_health())
            time.sleep(self._config.poll_interval_seconds)

        self.stop_all()

    def snapshot_health(self) -> dict[str, Any]:
        services: dict[str, Any] = {}
        for name, managed in self._procs.items():
            code = managed.process.poll()
            health = self._run_healthcheck(managed.spec)
            services[name] = {
                "pid": managed.process.pid,
                "running": code is None,
                "exit_code": code,
                "started_at": managed.started_at,
                "healthcheck": health,
            }
        return {
            "status": "stopping" if self._stopping else "running",
            "device_id": self._config.device_id,
            "timestamp": int(time.time()),
            "services": services,
        }

    def stop_all(self) -> None:
        for name in reversed(list(self._procs.keys())):
            self._stop_service(name)

        self._write_state({"status": "stopped", "timestamp": int(time.time())})

    def _prepare_paths(self) -> None:
        self._config.runtime_state_dir.mkdir(parents=True, exist_ok=True)
        self._config.log_dir.mkdir(parents=True, exist_ok=True)

    def _install_signal_handlers(self) -> None:
        signal.signal(signal.SIGTERM, self._on_signal)
        signal.signal(signal.SIGINT, self._on_signal)

    def _on_signal(self, _signum: int, _frame: Any) -> None:
        self._stopping = True

    def _start_in_dependency_order(self) -> None:
        pending = {svc.name: svc for svc in self._config.services}
        started: set[str] = set()

        while pending:
            progress = False
            for name, svc in list(pending.items()):
                if all(dep in started for dep in svc.start_after):
                    self._start_service(svc)
                    started.add(name)
                    del pending[name]
                    progress = True
            if not progress:
                missing = {k: v.start_after for k, v in pending.items()}
                raise RuntimeError(f"Dependency cycle or missing dependency in services: {missing}")

    def _start_service(self, spec: ServiceSpec) -> None:
        log_path = self._config.log_dir / f"{spec.name}.log"
        handle = log_path.open("a", encoding="utf-8")
        proc = subprocess.Popen(
            spec.command,
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        self._procs[spec.name] = ManagedProcess(
            spec=spec,
            process=proc,
            started_at=time.time(),
            log_handle=handle,
        )

    def _poll_processes(self) -> None:
        for name, managed in list(self._procs.items()):
            code = managed.process.poll()
            if code is None:
                continue

            if self._stopping:
                continue

            del self._procs[name]
            if managed.spec.restart == "always":
                self._start_service(managed.spec)
            elif managed.spec.restart == "on-failure" and code != 0:
                self._start_service(managed.spec)

    def _stop_service(self, name: str) -> None:
        managed = self._procs.get(name)
        if managed is None:
            return

        spec = managed.spec
        if spec.pre_stop:
            subprocess.run(spec.pre_stop, check=False)

        proc = managed.process
        if proc.poll() is None:
            proc.terminate()
            timeout = max(1, spec.stop_timeout_seconds)
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)

        try:
            managed.log_handle.close()
        except Exception:
            pass

        del self._procs[name]

    def _write_state(self, payload: dict[str, Any]) -> None:
        tmp = self._state_file.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
        tmp.replace(self._state_file)

    def _run_healthcheck(self, spec: ServiceSpec) -> dict[str, Any]:
        if not spec.healthcheck:
            cached = self._health.get(spec.name)
            return cached if cached is not None else {"ok": None, "detail": "not configured"}

        try:
            result = subprocess.run(
                spec.healthcheck,
                check=False,
                capture_output=True,
                text=True,
                timeout=3,
            )
            payload = {
                "ok": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            }
        except subprocess.TimeoutExpired:
            payload = {"ok": False, "returncode": None, "stdout": "", "stderr": "timeout"}
        self._health[spec.name] = payload
        return payload
