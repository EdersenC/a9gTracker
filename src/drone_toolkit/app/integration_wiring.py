"""Integration boundary for PX4 SITL assembly and scenario execution.

This module intentionally keeps imports late-bound so sibling agents can
implement their modules independently while keeping this integration surface
stable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple


class IntegrationWiringError(RuntimeError):
    """Raised when required integration factories are not discoverable."""


@dataclass(frozen=True)
class SITLScenarioResultV1:
    scenario_id: str
    passed: bool
    final_state: str
    expected_states: List[str]
    observed_states: List[str]
    failsafe_events: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)
    artifact_paths: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class IntegrationBundle:
    vehicle_port: Any
    mission_runtime: Any
    cli: Any = None


def _import_symbol(dotted_path: str) -> Any:
    module_name, _, symbol = dotted_path.rpartition(".")
    if not module_name:
        raise IntegrationWiringError(f"Invalid symbol path: {dotted_path}")
    module = importlib.import_module(module_name)
    return getattr(module, symbol)


def _load_first_available(
    symbol_candidates: Sequence[str],
    constructor_kwargs: Optional[Dict[str, Any]] = None,
) -> Any:
    constructor_kwargs = constructor_kwargs or {}
    last_err: Optional[Exception] = None
    for candidate in symbol_candidates:
        try:
            resolved = _import_symbol(candidate)
            if callable(resolved):
                return resolved(**constructor_kwargs)
            return resolved
        except Exception as err:  # pragma: no cover - compatibility shim
            last_err = err
    raise IntegrationWiringError(
        f"Unable to load any candidate symbol from: {symbol_candidates}"
    ) from last_err


def build_integration(
    *,
    config: Optional[Dict[str, Any]] = None,
    vehicle_factory: Optional[Callable[..., Any]] = None,
    runtime_factory: Optional[Callable[..., Any]] = None,
    cli_factory: Optional[Callable[..., Any]] = None,
) -> IntegrationBundle:
    """Compose adapter/runtime/sdk at the single integration boundary."""

    config = config or {}

    if vehicle_factory is None:
        vehicle_factory = lambda **kwargs: _load_first_available(  # noqa: E731
            [
                "drone_toolkit.adapters.mavlink.factory.create_vehicle_port",
                "drone_toolkit.adapters.mavlink.px4.create_vehicle_port",
                "drone_toolkit.adapters.mavlink.px4.create_px4_vehicle_port",
            ],
            kwargs,
        )
    if runtime_factory is None:
        runtime_factory = lambda **kwargs: _load_first_available(  # noqa: E731
            [
                "drone_toolkit.runtime.factory.create_mission_runtime",
                "drone_toolkit.runtime.mission_runtime.create_mission_runtime",
            ],
            kwargs,
        )
    if cli_factory is None:
        cli_factory = lambda **kwargs: _load_first_available(  # noqa: E731
            [
                "drone_toolkit.cli.factory.create_cli",
                "drone_toolkit.sdk.factory.create_cli",
            ],
            kwargs,
        )

    vehicle_cfg = config.get("vehicle", {})
    runtime_cfg = config.get("runtime", {})
    cli_cfg = config.get("cli", {})

    vehicle_port = vehicle_factory(**vehicle_cfg)
    mission_runtime = runtime_factory(vehicle_port=vehicle_port, **runtime_cfg)

    cli = None
    try:
        cli = cli_factory(runtime=mission_runtime, vehicle_port=vehicle_port, **cli_cfg)
    except Exception:
        # CLI may be optional for scenario-only execution.
        cli = None

    return IntegrationBundle(
        vehicle_port=vehicle_port,
        mission_runtime=mission_runtime,
        cli=cli,
    )


def _utc_now_iso8601() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _extract_event_kind(event: Any) -> str:
    if isinstance(event, dict):
        return str(event.get("kind") or event.get("type") or event.get("event") or "")
    return str(getattr(event, "kind", getattr(event, "type", "")))


def _event_to_dict(event: Any) -> Dict[str, Any]:
    if isinstance(event, dict):
        return dict(event)
    if hasattr(event, "__dict__"):
        return dict(vars(event))
    return {"value": str(event)}


class PX4SITLScenarioHarnessV1:
    """Scenario harness implementing PX4SITLScenarioContractV1 behavior."""

    def __init__(
        self,
        *,
        artifact_dir: str = "artifacts/sitl",
        integration_factory: Callable[..., IntegrationBundle] = build_integration,
    ) -> None:
        self.artifact_dir = Path(artifact_dir)
        self.integration_factory = integration_factory
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

    def run_scenario(
        self,
        *,
        scenario_id: str,
        mission_plan: Dict[str, Any],
        expected_terminal_states: Iterable[str],
        expected_failsafe_events: Iterable[str],
        runtime_event_sequence: Optional[Iterable[Any]] = None,
        runtime_state_sequence: Optional[Iterable[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        integration_bundle: Optional[IntegrationBundle] = None,
    ) -> SITLScenarioResultV1:
        """
        Execute a scenario and emit deterministic JSON trace artifacts.

        `runtime_event_sequence` and `runtime_state_sequence` are optional hooks
        used by tests to provide deterministic scenario traces without requiring
        a live simulator process.
        """

        metadata = metadata or {}
        expected_states = list(expected_terminal_states)
        expected_events = set(expected_failsafe_events)
        observed_states = list(runtime_state_sequence or [])
        raw_events = list(runtime_event_sequence or [])
        failsafe_events = [_event_to_dict(event) for event in raw_events]
        observed_event_kinds = {_extract_event_kind(event) for event in failsafe_events}

        if integration_bundle is not None and not observed_states:
            runtime = integration_bundle.mission_runtime
            runtime.start(mission_plan)
            if hasattr(runtime, "state_trace"):
                observed_states = list(runtime.state_trace())
            final_state = getattr(runtime, "get_state", lambda: "UNKNOWN")()
        else:
            final_state = observed_states[-1] if observed_states else "UNKNOWN"

        terminal_state_ok = final_state in expected_states
        events_ok = expected_events.issubset(observed_event_kinds)
        passed = terminal_state_ok and events_ok

        trace = {
            "scenario_id": scenario_id,
            "timestamp_utc": _utc_now_iso8601(),
            "passed": passed,
            "final_state": final_state,
            "expected_states": expected_states,
            "observed_states": observed_states,
            "expected_failsafe_events": sorted(expected_events),
            "failsafe_events": failsafe_events,
            "metadata": metadata,
        }
        trace_path = self.artifact_dir / f"{scenario_id}.trace.json"
        trace_path.write_text(json.dumps(trace, indent=2, sort_keys=True), encoding="utf-8")

        result = SITLScenarioResultV1(
            scenario_id=scenario_id,
            passed=passed,
            final_state=final_state,
            expected_states=expected_states,
            observed_states=observed_states,
            failsafe_events=failsafe_events,
            metadata=metadata,
            artifact_paths={"json_trace": str(trace_path)},
        )

        result_path = self.artifact_dir / f"{scenario_id}.result.json"
        result_path.write_text(
            json.dumps(asdict(result), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return result

