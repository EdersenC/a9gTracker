"""Mission runtime interface contracts (v1)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import AsyncIterator, Protocol, runtime_checkable

from .failsafe import FailsafeEventV1
from .mission_plan import MissionPlanV1
from .vehicle_port import VehiclePortV1


class RuntimeStateV1(str, Enum):
    """State machine states exposed by runtime."""

    IDLE = "IDLE"
    PRECHECK = "PRECHECK"
    ARMED = "ARMED"
    ENROUTE = "ENROUTE"
    RTH = "RTH"
    HOLD = "HOLD"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"
    FAILED = "FAILED"


class RuntimeEventKindV1(str, Enum):
    """Runtime event stream kinds."""

    STATE = "STATE"
    FAILSAFE = "FAILSAFE"
    INFO = "INFO"
    ERROR = "ERROR"


@dataclass(frozen=True)
class RuntimeEventV1:
    """Event payload emitted by MissionRuntimeAPI.event_stream()."""

    kind: RuntimeEventKindV1
    monotonic_ts_ms: int
    state: RuntimeStateV1 | None = None
    failsafe: FailsafeEventV1 | None = None
    message: str | None = None


@runtime_checkable
class MissionRuntimeAPI(Protocol):
    """Canonical runtime API consumed by SDK/CLI and SITL harness."""

    def __init__(self, vehicle_port: VehiclePortV1) -> None:
        """Bind runtime to a VehiclePortV1 implementation."""

    async def start(self, plan: MissionPlanV1) -> None:
        """Validate plan, run prechecks, and execute mission."""

    async def stop(self) -> None:
        """Stop runtime loop without forcing a mission abort."""

    async def abort(self, reason: str) -> None:
        """Abort active mission and emit MISSION_ABORT failsafe event."""

    async def get_state(self) -> RuntimeStateV1:
        """Read current runtime state."""

    def event_stream(self) -> AsyncIterator[RuntimeEventV1]:
        """Iterate runtime events including failsafe transitions."""
