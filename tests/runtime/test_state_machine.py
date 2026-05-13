import asyncio
import pathlib
import sys
from typing import Any, Callable

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from drone_toolkit.runtime.runtime_service import MissionRuntimeService
from drone_toolkit.runtime.state_machine import (
    InvalidTransitionError,
    MissionStateMachine,
    RuntimeEvent,
    RuntimeState,
)


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


def test_state_machine_nominal_transition_table() -> None:
    machine = MissionStateMachine()

    assert machine.state == RuntimeState.IDLE
    assert machine.transition(RuntimeEvent.START).state == RuntimeState.PRECHECK
    assert machine.transition(RuntimeEvent.PRECHECK_PASSED).state == RuntimeState.ARMED
    assert machine.transition(RuntimeEvent.MISSION_STARTED).state == RuntimeState.ENROUTE
    assert machine.transition(RuntimeEvent.MISSION_COMPLETED).state == RuntimeState.COMPLETED


def test_terminal_state_is_sticky() -> None:
    machine = MissionStateMachine()
    machine.transition(RuntimeEvent.START)
    machine.transition(RuntimeEvent.PRECHECK_PASSED)
    machine.transition(RuntimeEvent.MISSION_STARTED)
    machine.transition(RuntimeEvent.MISSION_COMPLETED)

    decision = machine.transition(RuntimeEvent.FAILSAFE_ABORT)
    assert decision.state == RuntimeState.COMPLETED
    assert decision.reason_code == "TERMINAL_COMPLETED"


def test_invalid_transition_raises() -> None:
    machine = MissionStateMachine()
    try:
        machine.transition(RuntimeEvent.MISSION_STARTED)
    except InvalidTransitionError:
        pass
    else:
        raise AssertionError("Expected InvalidTransitionError")


def test_runtime_nominal_lifecycle() -> None:
    async def run() -> None:
        vehicle = FakeVehiclePort()
        runtime = MissionRuntimeService(vehicle)
        plan = {
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

        state = await runtime.start(plan)
        assert state == RuntimeState.ENROUTE
        assert runtime.get_state() == RuntimeState.ENROUTE

        await runtime.complete_mission()
        assert runtime.get_state() == RuntimeState.COMPLETED

        call_names = [name for name, _ in vehicle.calls]
        assert call_names[:5] == ["connect", "upload_mission", "set_mode", "arm", "start_mission"]
        assert "disconnect" in call_names

    asyncio.run(run())
