"""Failsafe detection and policy mapping for mission runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import asin, cos, radians, sin, sqrt
from typing import Any, Iterable, Mapping

from .state_machine import RuntimeEvent


class FailsafeEventType(str, Enum):
    GEOFENCE_BREACH = "GEOFENCE_BREACH"
    LINK_LOSS = "LINK_LOSS"
    LOW_BATTERY = "LOW_BATTERY"
    MISSION_ABORT = "MISSION_ABORT"
    VEHICLE_ERROR = "VEHICLE_ERROR"


class FailsafeSeverity(str, Enum):
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class FailsafeEventV1:
    event_type: FailsafeEventType
    severity: FailsafeSeverity
    source: str
    reason_code: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FailsafeDecision:
    runtime_event: RuntimeEvent
    reason_code: str


class FailsafePolicy:
    """Evaluates telemetry and maps canonical failsafe events to runtime events."""

    def __init__(self, low_battery_threshold_pct: float = 20.0) -> None:
        self.low_battery_threshold_pct = low_battery_threshold_pct

    def evaluate_telemetry(self, frame: Any, plan: Any) -> list[FailsafeEventV1]:
        events: list[FailsafeEventV1] = []

        link_state = _extract_value(frame, "link_state")
        if link_state is not None and not _is_link_up(link_state):
            events.append(
                FailsafeEventV1(
                    event_type=FailsafeEventType.LINK_LOSS,
                    severity=FailsafeSeverity.CRITICAL,
                    source="telemetry",
                    reason_code="LINK_LOSS",
                    metadata={"link_state": str(link_state)},
                )
            )

        battery_pct = _extract_value(frame, "battery_pct")
        if isinstance(battery_pct, (int, float)) and battery_pct <= self.low_battery_threshold_pct:
            events.append(
                FailsafeEventV1(
                    event_type=FailsafeEventType.LOW_BATTERY,
                    severity=FailsafeSeverity.WARNING,
                    source="telemetry",
                    reason_code="LOW_BATTERY",
                    metadata={"battery_pct": battery_pct},
                )
            )

        position = _extract_value(frame, "position")
        if position and _is_outside_geofence(plan, position):
            events.append(
                FailsafeEventV1(
                    event_type=FailsafeEventType.GEOFENCE_BREACH,
                    severity=FailsafeSeverity.CRITICAL,
                    source="telemetry",
                    reason_code="GEOFENCE_BREACH",
                    metadata={"position": position},
                )
            )

        health_flags = _extract_value(frame, "health_flags")
        if _has_vehicle_error(health_flags):
            events.append(
                FailsafeEventV1(
                    event_type=FailsafeEventType.VEHICLE_ERROR,
                    severity=FailsafeSeverity.CRITICAL,
                    source="telemetry",
                    reason_code="VEHICLE_ERROR",
                )
            )

        return events

    def mission_abort_event(self, reason: str) -> FailsafeEventV1:
        return FailsafeEventV1(
            event_type=FailsafeEventType.MISSION_ABORT,
            severity=FailsafeSeverity.CRITICAL,
            source="operator",
            reason_code="MISSION_ABORT",
            metadata={"reason": reason},
        )

    def decision_for(self, event: FailsafeEventV1) -> FailsafeDecision:
        if event.event_type == FailsafeEventType.GEOFENCE_BREACH:
            return FailsafeDecision(runtime_event=RuntimeEvent.FAILSAFE_HOLD, reason_code="FS_GEOFENCE_HOLD")
        if event.event_type == FailsafeEventType.LINK_LOSS:
            return FailsafeDecision(runtime_event=RuntimeEvent.FAILSAFE_RTH, reason_code="FS_LINK_LOSS_RTH")
        if event.event_type == FailsafeEventType.LOW_BATTERY:
            return FailsafeDecision(runtime_event=RuntimeEvent.FAILSAFE_RTH, reason_code="FS_LOW_BATTERY_RTH")
        if event.event_type == FailsafeEventType.MISSION_ABORT:
            return FailsafeDecision(runtime_event=RuntimeEvent.FAILSAFE_ABORT, reason_code="FS_MISSION_ABORT")
        return FailsafeDecision(runtime_event=RuntimeEvent.VEHICLE_ERROR, reason_code="FS_VEHICLE_ERROR")


def _extract_value(data: Any, key: str) -> Any:
    if isinstance(data, Mapping):
        return data.get(key)
    return getattr(data, key, None)


def _is_link_up(link_state: Any) -> bool:
    if isinstance(link_state, bool):
        return link_state
    normalized = str(link_state).strip().upper()
    return normalized in {"UP", "CONNECTED", "HEALTHY", "TRUE", "1"}


def _has_vehicle_error(health_flags: Any) -> bool:
    if health_flags is None:
        return False
    if isinstance(health_flags, Mapping):
        return any(
            bool(health_flags.get(key))
            for key in ("vehicle_error", "critical_error", "error", "fault")
        )
    if isinstance(health_flags, (list, tuple, set)):
        normalized = {str(item).strip().lower() for item in health_flags}
        return any(token in normalized for token in {"vehicle_error", "critical_error", "error", "fault"})
    return False


def _is_outside_geofence(plan: Any, position: Any) -> bool:
    geofence = _extract_value(plan, "geofence")
    if not geofence:
        return False

    lat = _extract_value(position, "lat")
    lon = _extract_value(position, "lon")
    if lat is None or lon is None:
        return False

    if isinstance(geofence, Mapping) and "polygon" in geofence:
        polygon = geofence.get("polygon")
        if polygon:
            return not _point_in_polygon(lat, lon, polygon)

    if isinstance(geofence, Mapping) and "cylinder" in geofence:
        cylinder = geofence.get("cylinder") or {}
        center = cylinder.get("center") or {}
        radius_m = cylinder.get("radius_m")
        clat = _extract_value(center, "lat")
        clon = _extract_value(center, "lon")
        if all(v is not None for v in (clat, clon, radius_m)):
            return _distance_m(lat, lon, clat, clon) > float(radius_m)

    return False


def _point_in_polygon(lat: float, lon: float, polygon: Iterable[Any]) -> bool:
    points: list[tuple[float, float]] = []
    for vertex in polygon:
        vlat = _extract_value(vertex, "lat")
        vlon = _extract_value(vertex, "lon")
        if vlat is None or vlon is None:
            continue
        points.append((float(vlat), float(vlon)))

    if len(points) < 3:
        return True

    inside = False
    j = len(points) - 1
    for i, point in enumerate(points):
        yi, xi = point
        yj, xj = points[j]
        intersects = ((xi > lon) != (xj > lon)) and (
            lat < (yj - yi) * (lon - xi) / ((xj - xi) or 1e-12) + yi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    lat1r = radians(lat1)
    lat2r = radians(lat2)
    hav = sin(dlat / 2) ** 2 + cos(lat1r) * cos(lat2r) * sin(dlon / 2) ** 2
    return 2 * radius * asin(sqrt(hav))
