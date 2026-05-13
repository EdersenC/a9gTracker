"""Failsafe contracts (v1)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FailsafeEventTypeV1(str, Enum):
    """Event taxonomy that runtime policy consumes."""

    GEOFENCE_BREACH = "GEOFENCE_BREACH"
    LINK_LOSS = "LINK_LOSS"
    LOW_BATTERY = "LOW_BATTERY"
    MISSION_ABORT = "MISSION_ABORT"
    VEHICLE_ERROR = "VEHICLE_ERROR"


class FailsafeSeverityV1(str, Enum):
    """Severity level used for observability and policy."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class FailsafeSourceV1(str, Enum):
    """Origin of a failsafe event."""

    RUNTIME = "RUNTIME"
    VEHICLE = "VEHICLE"
    OPERATOR = "OPERATOR"
    SYSTEM = "SYSTEM"


class FailsafeActionV1(str, Enum):
    """Policy action selected by runtime state machine."""

    HOLD = "HOLD"
    RTH = "RTH"
    ABORT = "ABORT"


@dataclass(frozen=True)
class FailsafeEventV1:
    """Canonical failsafe event payload."""

    event_type: FailsafeEventTypeV1
    severity: FailsafeSeverityV1
    source: FailsafeSourceV1
    monotonic_ts_ms: int
    reason: str
    details: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if self.monotonic_ts_ms < 0:
            raise ValueError("monotonic_ts_ms must be >= 0")
        if not self.reason:
            raise ValueError("reason must be non-empty")


DEFAULT_FAILSAFE_ACTIONS_V1: dict[FailsafeEventTypeV1, FailsafeActionV1] = {
    FailsafeEventTypeV1.GEOFENCE_BREACH: FailsafeActionV1.RTH,
    FailsafeEventTypeV1.LINK_LOSS: FailsafeActionV1.HOLD,
    FailsafeEventTypeV1.LOW_BATTERY: FailsafeActionV1.RTH,
    FailsafeEventTypeV1.MISSION_ABORT: FailsafeActionV1.ABORT,
    FailsafeEventTypeV1.VEHICLE_ERROR: FailsafeActionV1.ABORT,
}
