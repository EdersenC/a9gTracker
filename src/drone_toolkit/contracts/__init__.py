"""Shared v1 contracts for mission runtime, adapter, and SDK/CLI."""

from .failsafe import (
    DEFAULT_FAILSAFE_ACTIONS_V1,
    FailsafeActionV1,
    FailsafeEventTypeV1,
    FailsafeEventV1,
    FailsafeSeverityV1,
    FailsafeSourceV1,
)
from .mission_plan import (
    AltitudePolicyV1,
    GeofenceTypeV1,
    GeofenceV1,
    GeoPointV1,
    MissionPlanV1,
    MissionPlanValidationCodeV1,
    MissionPlanValidationErrorV1,
    MissionPlanValidationExceptionV1,
    RTHPolicyV1,
    TimeoutPolicyV1,
    WaypointV1,
)
from .runtime_api import MissionRuntimeAPI, RuntimeEventKindV1, RuntimeEventV1, RuntimeStateV1
from .telemetry import GPSFixV1, LinkStateV1, MissionProgressV1, PositionV1, TelemetryFrameV1
from .vehicle_port import (
    TelemetrySubscriptionV1,
    VehicleCommandErrorCodeV1,
    VehicleCommandErrorV1,
    VehiclePortV1,
)

__all__ = [
    "AltitudePolicyV1",
    "DEFAULT_FAILSAFE_ACTIONS_V1",
    "FailsafeActionV1",
    "FailsafeEventTypeV1",
    "FailsafeEventV1",
    "FailsafeSeverityV1",
    "FailsafeSourceV1",
    "GPSFixV1",
    "GeofenceTypeV1",
    "GeofenceV1",
    "GeoPointV1",
    "LinkStateV1",
    "MissionPlanV1",
    "MissionPlanValidationCodeV1",
    "MissionPlanValidationErrorV1",
    "MissionPlanValidationExceptionV1",
    "MissionProgressV1",
    "MissionRuntimeAPI",
    "PositionV1",
    "RTHPolicyV1",
    "RuntimeEventKindV1",
    "RuntimeEventV1",
    "RuntimeStateV1",
    "TelemetryFrameV1",
    "TelemetrySubscriptionV1",
    "TimeoutPolicyV1",
    "VehicleCommandErrorCodeV1",
    "VehicleCommandErrorV1",
    "VehiclePortV1",
    "WaypointV1",
]
