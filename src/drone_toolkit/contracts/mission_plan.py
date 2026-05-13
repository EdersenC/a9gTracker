"""Mission plan contracts (v1)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MissionPlanValidationCodeV1(str, Enum):
    """Stable validation codes for v1.x compatibility."""

    MISSION_ID_REQUIRED = "MISSION_ID_REQUIRED"
    HOME_POSITION_REQUIRED = "HOME_POSITION_REQUIRED"
    WAYPOINTS_REQUIRED = "WAYPOINTS_REQUIRED"
    WAYPOINT_ALTITUDE_INVALID = "WAYPOINT_ALTITUDE_INVALID"
    WAYPOINT_LAT_LON_INVALID = "WAYPOINT_LAT_LON_INVALID"
    CRUISE_SPEED_INVALID = "CRUISE_SPEED_INVALID"
    GEOFENCE_INVALID = "GEOFENCE_INVALID"
    TIMEOUT_INVALID = "TIMEOUT_INVALID"


@dataclass(frozen=True)
class MissionPlanValidationErrorV1:
    """Single validation issue in a mission plan."""

    code: MissionPlanValidationCodeV1
    field: str
    message: str


class MissionPlanValidationExceptionV1(ValueError):
    """Raised when a mission plan fails strict validation."""

    def __init__(self, errors: list[MissionPlanValidationErrorV1]) -> None:
        self.errors = errors
        msg = "; ".join(f"{err.code}:{err.field}" for err in errors)
        super().__init__(msg)


@dataclass(frozen=True)
class GeoPointV1:
    """WGS84 coordinate with optional altitude in meters."""

    lat: float
    lon: float
    alt_m: float | None = None


@dataclass(frozen=True)
class WaypointV1:
    """Mission waypoint definition."""

    position: GeoPointV1
    hold_time_s: float = 0.0


class GeofenceTypeV1(str, Enum):
    """Supported geofence shape for MVP."""

    POLYGON = "POLYGON"
    CYLINDER = "CYLINDER"


@dataclass(frozen=True)
class GeofenceV1:
    """Polygon or cylinder geofence for mission safety."""

    geofence_type: GeofenceTypeV1
    vertices: tuple[GeoPointV1, ...] = ()
    center: GeoPointV1 | None = None
    radius_m: float | None = None
    min_alt_m: float | None = None
    max_alt_m: float | None = None


@dataclass(frozen=True)
class RTHPolicyV1:
    """Return-to-home policy knobs for failsafe behavior."""

    low_battery_threshold_pct: float
    return_altitude_m: float


@dataclass(frozen=True)
class AltitudePolicyV1:
    """Altitude envelope for mission execution."""

    min_alt_m: float
    max_alt_m: float


@dataclass(frozen=True)
class TimeoutPolicyV1:
    """Timeout values in seconds."""

    precheck_timeout_s: float
    mission_timeout_s: float
    command_timeout_s: float


@dataclass(frozen=True)
class MissionPlanV1:
    """Canonical mission plan schema consumed by runtime and adapter."""

    mission_id: str
    home_position: GeoPointV1
    waypoints: tuple[WaypointV1, ...]
    geofence: GeofenceV1 | None
    rth_policy: RTHPolicyV1
    cruise_speed_mps: float
    altitude_policy: AltitudePolicyV1
    timeout_policy: TimeoutPolicyV1

    def __post_init__(self) -> None:
        errors = self.validate()
        if errors:
            raise MissionPlanValidationExceptionV1(errors)

    def validate(self) -> list[MissionPlanValidationErrorV1]:
        """Return a complete list of validation errors."""

        errors: list[MissionPlanValidationErrorV1] = []

        if not self.mission_id:
            errors.append(
                MissionPlanValidationErrorV1(
                    MissionPlanValidationCodeV1.MISSION_ID_REQUIRED,
                    "mission_id",
                    "mission_id must be non-empty",
                )
            )

        if self.home_position is None:
            errors.append(
                MissionPlanValidationErrorV1(
                    MissionPlanValidationCodeV1.HOME_POSITION_REQUIRED,
                    "home_position",
                    "home_position is required",
                )
            )

        if not self.waypoints:
            errors.append(
                MissionPlanValidationErrorV1(
                    MissionPlanValidationCodeV1.WAYPOINTS_REQUIRED,
                    "waypoints",
                    "at least one waypoint is required",
                )
            )

        for idx, wp in enumerate(self.waypoints):
            if not (-90.0 <= wp.position.lat <= 90.0) or not (-180.0 <= wp.position.lon <= 180.0):
                errors.append(
                    MissionPlanValidationErrorV1(
                        MissionPlanValidationCodeV1.WAYPOINT_LAT_LON_INVALID,
                        f"waypoints[{idx}].position",
                        "waypoint latitude/longitude out of range",
                    )
                )
            if wp.position.alt_m is None or wp.position.alt_m <= 0.0:
                errors.append(
                    MissionPlanValidationErrorV1(
                        MissionPlanValidationCodeV1.WAYPOINT_ALTITUDE_INVALID,
                        f"waypoints[{idx}].position.alt_m",
                        "waypoint altitude must be > 0",
                    )
                )

        if self.cruise_speed_mps <= 0.0:
            errors.append(
                MissionPlanValidationErrorV1(
                    MissionPlanValidationCodeV1.CRUISE_SPEED_INVALID,
                    "cruise_speed_mps",
                    "cruise_speed_mps must be > 0",
                )
            )

        if self.timeout_policy.precheck_timeout_s <= 0.0:
            errors.append(
                MissionPlanValidationErrorV1(
                    MissionPlanValidationCodeV1.TIMEOUT_INVALID,
                    "timeout_policy.precheck_timeout_s",
                    "precheck timeout must be > 0",
                )
            )

        if self.timeout_policy.command_timeout_s <= 0.0:
            errors.append(
                MissionPlanValidationErrorV1(
                    MissionPlanValidationCodeV1.TIMEOUT_INVALID,
                    "timeout_policy.command_timeout_s",
                    "command timeout must be > 0",
                )
            )

        if self.timeout_policy.mission_timeout_s <= 0.0:
            errors.append(
                MissionPlanValidationErrorV1(
                    MissionPlanValidationCodeV1.TIMEOUT_INVALID,
                    "timeout_policy.mission_timeout_s",
                    "mission timeout must be > 0",
                )
            )

        if self.geofence is not None:
            errors.extend(self._validate_geofence())

        return errors

    def _validate_geofence(self) -> list[MissionPlanValidationErrorV1]:
        errors: list[MissionPlanValidationErrorV1] = []
        geofence = self.geofence
        assert geofence is not None

        if geofence.geofence_type == GeofenceTypeV1.POLYGON:
            if len(geofence.vertices) < 3:
                errors.append(
                    MissionPlanValidationErrorV1(
                        MissionPlanValidationCodeV1.GEOFENCE_INVALID,
                        "geofence.vertices",
                        "polygon geofence must include at least 3 vertices",
                    )
                )
        elif geofence.geofence_type == GeofenceTypeV1.CYLINDER:
            if geofence.center is None or geofence.radius_m is None or geofence.radius_m <= 0.0:
                errors.append(
                    MissionPlanValidationErrorV1(
                        MissionPlanValidationCodeV1.GEOFENCE_INVALID,
                        "geofence",
                        "cylinder geofence requires center and radius_m > 0",
                    )
                )
        else:
            errors.append(
                MissionPlanValidationErrorV1(
                    MissionPlanValidationCodeV1.GEOFENCE_INVALID,
                    "geofence.geofence_type",
                    "unsupported geofence type",
                )
            )

        if geofence.min_alt_m is not None and geofence.max_alt_m is not None:
            if geofence.min_alt_m > geofence.max_alt_m:
                errors.append(
                    MissionPlanValidationErrorV1(
                        MissionPlanValidationCodeV1.GEOFENCE_INVALID,
                        "geofence.min_alt_m",
                        "min_alt_m must be <= max_alt_m",
                    )
                )
        return errors
