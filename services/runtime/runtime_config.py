from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    command: list[str]
    start_after: list[str]
    restart: str
    stop_timeout_seconds: int
    healthcheck: list[str] | None
    pre_stop: list[str] | None


@dataclass(frozen=True)
class RuntimeConfig:
    device_id: str
    runtime_state_dir: Path
    log_dir: Path
    poll_interval_seconds: float
    startup_grace_seconds: int
    shutdown_grace_seconds: int
    services: list[ServiceSpec]


def _require_mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a mapping")
    return value


def _require_list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    return value


def _as_str_list(value: Any, field: str) -> list[str]:
    values = _require_list(value, field)
    if not all(isinstance(item, str) for item in values):
        raise ValueError(f"{field} must contain only strings")
    return values


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency PyYAML. Install with: pip install pyyaml"
        ) from exc

    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)

    if not isinstance(payload, dict):
        raise ValueError(f"Runtime config at {path} must be a mapping")

    return payload


def load_runtime_config(path: str | Path) -> RuntimeConfig:
    config_path = Path(path)
    raw = _load_yaml(config_path)

    runtime_raw = _require_mapping(raw.get("runtime", {}), "runtime")
    services_raw = _require_list(raw.get("services", []), "services")

    services: list[ServiceSpec] = []
    for idx, item in enumerate(services_raw):
        entry = _require_mapping(item, f"services[{idx}]")
        services.append(
            ServiceSpec(
                name=str(entry["name"]),
                command=_as_str_list(entry["command"], f"services[{idx}].command"),
                start_after=_as_str_list(entry.get("start_after", []), f"services[{idx}].start_after"),
                restart=str(entry.get("restart", "always")),
                stop_timeout_seconds=int(entry.get("stop_timeout_seconds", 15)),
                healthcheck=_as_str_list(entry["healthcheck"], f"services[{idx}].healthcheck")
                if entry.get("healthcheck") is not None
                else None,
                pre_stop=_as_str_list(entry["pre_stop"], f"services[{idx}].pre_stop")
                if entry.get("pre_stop") is not None
                else None,
            )
        )

    return RuntimeConfig(
        device_id=str(runtime_raw.get("device_id", "dashcam-rpi")),
        runtime_state_dir=Path(str(runtime_raw.get("runtime_state_dir", "/var/lib/dashcam-runtime/state"))),
        log_dir=Path(str(runtime_raw.get("log_dir", "/var/log/dashcam-runtime"))),
        poll_interval_seconds=float(runtime_raw.get("poll_interval_seconds", 2.0)),
        startup_grace_seconds=int(runtime_raw.get("startup_grace_seconds", 20)),
        shutdown_grace_seconds=int(runtime_raw.get("shutdown_grace_seconds", 20)),
        services=services,
    )
