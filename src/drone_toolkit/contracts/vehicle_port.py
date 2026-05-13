"""Vehicle adapter boundary contracts (v1)."""

from __future__ import annotations

from enum import Enum
from typing import Awaitable, Callable, Protocol, runtime_checkable

from .mission_plan import MissionPlanV1
from .telemetry import TelemetryFrameV1


class VehicleCommandErrorCodeV1(str, Enum):
    """Stable vehicle command error taxonomy."""

    DISCONNECTED = "DISCONNECTED"
    ARM_DENIED = "ARM_DENIED"
    MODE_REJECTED = "MODE_REJECTED"
    MISSION_UPLOAD_FAILED = "MISSION_UPLOAD_FAILED"
    COMMAND_TIMEOUT = "COMMAND_TIMEOUT"
    INVALID_COMMAND = "INVALID_COMMAND"
    UNSUPPORTED = "UNSUPPORTED"
    INTERNAL = "INTERNAL"


class VehicleCommandErrorV1(RuntimeError):
    """Raised when an adapter command fails."""

    def __init__(self, code: VehicleCommandErrorCodeV1, message: str, retryable: bool = False) -> None:
        self.code = code
        self.retryable = retryable
        super().__init__(message)


TelemetryCallbackV1 = Callable[[TelemetryFrameV1], Awaitable[None] | None]


@runtime_checkable
class TelemetrySubscriptionV1(Protocol):
    """Telemetry subscription endpoint."""

    async def subscribe(self, callback: TelemetryCallbackV1) -> None:
        """Register a callback that receives telemetry frames."""


@runtime_checkable
class VehiclePortV1(Protocol):
    """Canonical vehicle command and telemetry interface for v1."""

    telemetry: TelemetrySubscriptionV1

    async def connect(self) -> None:
        """Open adapter connection and initialize command session."""

    async def arm(self) -> None:
        """Arm vehicle for mission execution."""

    async def set_mode(self, mode: str) -> None:
        """Set a flight mode by normalized mode name."""

    async def upload_mission(self, plan: MissionPlanV1) -> None:
        """Upload validated mission plan to vehicle."""

    async def start_mission(self) -> None:
        """Start the uploaded mission."""

    async def goto_home(self) -> None:
        """Trigger return-to-home behavior."""

    async def hold(self) -> None:
        """Command immediate hold behavior."""

    async def abort(self, reason: str) -> None:
        """Abort mission execution with operator/runtime reason."""

    async def disconnect(self) -> None:
        """Close adapter connection and release resources."""
