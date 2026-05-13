import asyncio
import pathlib
import sys
from typing import Any, Callable

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from drone_toolkit.runtime.runtime_service import MissionRuntimeService
from drone_toolkit.runtime.state_machine import RuntimeState


class FakeVehiclePort:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self._callback: Callable[[Any], None] | None = None

    async def connect(self) -> None:
        self.calls.append(("connect", None))

    async def arm(self) -> None:
        self.calls.append(("arm", None))

    async def set_mode(self, mode: str) -> None:
        self.calls.append(("set_mode", mode))

    async def upload_mission(self, plan: Any) -> None:
        self.calls.append(("upload_mission", plan))

    async def start_mission(self) -> None:
        self.calls.append(("start_mission", None))

    async def goto_home(self) -> None:
        self.calls.append(("goto_home", None))

    async def hold(self) -> None:
        self.calls.append(("hold", None))

    async def abort(self, reason: str) -> None:
        self.calls.append(("abort", reason))

    async def disconnect(self) -> None:
        self.calls.append(("disconnect", None))

    def subscribe(self, callback: Callable[[Any], None]) -> Callable[[], None]:
        self._callback = callback

        def unsubscribe() -> None:
            self._callback = None

        return unsubscribe

    async def emit(self, frame: Any) -> None:
        if self._callback is not None:
            self._callback(frame)
        await asyncio.sleep(0)


def _plan() -> dict[str, Any]:
    return {
        "mission_id": "m1",
        "geofence": {
            "polygon": [
                {"lat": 0.0, "lon": 0.0},
                {"lat": 0.0, "lon": 1.0},
                {"lat": 1.0, "lon": 1.0},
                {"lat": 1.0, "lon": 0.0},
            ]
        },
    }


def _has_call(calls: list[tuple[str, Any]], name: str) -> bool:
    return any(call_name == name for call_name, _ in calls)


def _failsafe_types(runtime: MissionRuntimeService) -> list[str]:
    event_types: list[str] = []
    while not runtime._events.empty():  # noqa: SLF001 - test-only inspection
        record = runtime._events.get_nowait()  # noqa: SLF001 - test-only inspection
        if record.kind == "FAILSAFE_EVENT":
            event_types.append(str(record.data.get("event_type")))
    return event_types


def test_geofence_breach_transitions_to_hold() -> None:
    async def run() -> None:
        vehicle = FakeVehiclePort()
        runtime = MissionRuntimeService(vehicle)
        await runtime.start(_plan())

        await vehicle.emit(
            {
                "position": {"lat": 5.0, "lon": 5.0},
                "battery_pct": 80,
                "link_state": "UP",
                "health_flags": {},
            }
        )

        assert runtime.get_state() == RuntimeState.HOLD
        assert _has_call(vehicle.calls, "hold")
        assert "GEOFENCE_BREACH" in _failsafe_types(runtime)

    asyncio.run(run())


def test_link_loss_transitions_to_rth() -> None:
    async def run() -> None:
        vehicle = FakeVehiclePort()
        runtime = MissionRuntimeService(vehicle)
        await runtime.start(_plan())

        await vehicle.emit(
            {
                "position": {"lat": 0.5, "lon": 0.5},
                "battery_pct": 80,
                "link_state": "DOWN",
                "health_flags": {},
            }
        )

        assert runtime.get_state() == RuntimeState.RTH
        assert _has_call(vehicle.calls, "goto_home")
        assert "LINK_LOSS" in _failsafe_types(runtime)

    asyncio.run(run())


def test_low_battery_transitions_to_rth() -> None:
    async def run() -> None:
        vehicle = FakeVehiclePort()
        runtime = MissionRuntimeService(vehicle)
        await runtime.start(_plan())

        await vehicle.emit(
            {
                "position": {"lat": 0.5, "lon": 0.5},
                "battery_pct": 10,
                "link_state": "UP",
                "health_flags": {},
            }
        )

        assert runtime.get_state() == RuntimeState.RTH
        assert _has_call(vehicle.calls, "goto_home")
        assert "LOW_BATTERY" in _failsafe_types(runtime)

    asyncio.run(run())


def test_vehicle_error_transitions_to_failed() -> None:
    async def run() -> None:
        vehicle = FakeVehiclePort()
        runtime = MissionRuntimeService(vehicle)
        await runtime.start(_plan())

        await vehicle.emit(
            {
                "position": {"lat": 0.5, "lon": 0.5},
                "battery_pct": 80,
                "link_state": "UP",
                "health_flags": {"error": True},
            }
        )

        assert runtime.get_state() == RuntimeState.FAILED
        assert _has_call(vehicle.calls, "abort")
        assert _has_call(vehicle.calls, "disconnect")
        assert "VEHICLE_ERROR" in _failsafe_types(runtime)

    asyncio.run(run())


def test_operator_abort_transitions_to_aborted() -> None:
    async def run() -> None:
        vehicle = FakeVehiclePort()
        runtime = MissionRuntimeService(vehicle)
        await runtime.start(_plan())

        await runtime.abort("operator requested")

        assert runtime.get_state() == RuntimeState.ABORTED
        assert _has_call(vehicle.calls, "abort")
        assert _has_call(vehicle.calls, "disconnect")
        assert "MISSION_ABORT" in _failsafe_types(runtime)

    asyncio.run(run())
