"""Telemetry contracts (v1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class GPSFixV1(str, Enum):
    """Normalized GPS fix quality used across adapters."""

    NONE = "NONE"
    FIX_2D = "FIX_2D"
    FIX_3D = "FIX_3D"
    DGPS = "DGPS"
    RTK = "RTK"


class LinkStateV1(str, Enum):
    """Normalized link state from adapter to runtime."""

    UP = "UP"
    DEGRADED = "DEGRADED"
    LOST = "LOST"


@dataclass(frozen=True)
class PositionV1:
    """WGS84 position plus altitude in meters."""

    lat: float
    lon: float
    alt_m: float

    def __post_init__(self) -> None:
        if not (-90.0 <= self.lat <= 90.0):
            raise ValueError("position.lat must be within [-90, 90]")
        if not (-180.0 <= self.lon <= 180.0):
            raise ValueError("position.lon must be within [-180, 180]")


@dataclass(frozen=True)
class MissionProgressV1:
    """Mission waypoint progress counters."""

    current_wp: int
    total_wp: int

    def __post_init__(self) -> None:
        if self.total_wp < 0:
            raise ValueError("mission_progress.total_wp must be >= 0")
        if self.current_wp < 0:
            raise ValueError("mission_progress.current_wp must be >= 0")
        if self.total_wp > 0 and self.current_wp > self.total_wp:
            raise ValueError("mission_progress.current_wp must be <= total_wp")


@dataclass(frozen=True)
class TelemetryFrameV1:
    """Canonical telemetry frame consumed by runtime and CLI."""

    monotonic_ts_ms: int
    wall_ts_iso8601: str
    position: PositionV1
    velocity_mps: float
    heading_deg: float
    battery_pct: float
    gps_fix: GPSFixV1
    link_state: LinkStateV1
    flight_mode: str
    armed: bool
    mission_progress: MissionProgressV1
    health_flags: frozenset[str] = field(default_factory=frozenset)
    optional_fields: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.monotonic_ts_ms < 0:
            raise ValueError("monotonic_ts_ms must be >= 0")
        if not (0.0 <= self.heading_deg < 360.0):
            raise ValueError("heading_deg must be within [0, 360)")
        if not (0.0 <= self.battery_pct <= 100.0):
            raise ValueError("battery_pct must be within [0, 100]")
        if not self.wall_ts_iso8601:
            raise ValueError("wall_ts_iso8601 must be non-empty")
        if not self.flight_mode:
            raise ValueError("flight_mode must be non-empty")
