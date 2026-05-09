from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .errors import ValidationError


_REQUIRED_FIELDS = ("trackerId", "timestamp", "lat", "lon")
_OPTIONAL_FIELDS = ("speed", "heading", "accuracy")


def normalize_tracker_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValidationError(
            "Invalid tracker payload",
            details=[{"field": "$", "message": "Payload must be a JSON object"}],
        )

    details: list[dict[str, Any]] = []
    missing = [name for name in _REQUIRED_FIELDS if name not in payload]
    for name in missing:
        details.append({"field": name, "message": "Field is required"})

    tracker_id = payload.get("trackerId")
    if tracker_id is not None:
        if not isinstance(tracker_id, str) or not tracker_id.strip():
            details.append(
                {"field": "trackerId", "message": "trackerId must be a non-empty string"}
            )

    timestamp_raw = payload.get("timestamp")
    timestamp: str | None = None
    if timestamp_raw is not None:
        timestamp = _normalize_timestamp(timestamp_raw, details)

    lat = _coerce_number(payload.get("lat"), "lat", details)
    lon = _coerce_number(payload.get("lon"), "lon", details)

    if lat is not None and not -90 <= lat <= 90:
        details.append({"field": "lat", "message": "lat must be in the range [-90, 90]"})
    if lon is not None and not -180 <= lon <= 180:
        details.append({"field": "lon", "message": "lon must be in the range [-180, 180]"})

    optional: dict[str, Any] = {}
    for field_name in _OPTIONAL_FIELDS:
        if field_name not in payload:
            continue
        number = _coerce_number(payload.get(field_name), field_name, details)
        if number is None:
            continue
        if field_name in {"speed", "accuracy"} and number < 0:
            details.append({"field": field_name, "message": f"{field_name} cannot be negative"})
        if field_name == "heading" and not 0 <= number <= 360:
            details.append({"field": "heading", "message": "heading must be in the range [0, 360]"})
        optional[field_name] = number

    if details:
        raise ValidationError("Invalid tracker payload", details)

    normalized: dict[str, Any] = {
        "trackerId": tracker_id.strip(),
        "timestamp": timestamp,
        "lat": lat,
        "lon": lon,
    }
    normalized.update(optional)
    return normalized


def _coerce_number(value: Any, field_name: str, details: list[dict[str, Any]]) -> float | None:
    if isinstance(value, bool) or value is None:
        details.append({"field": field_name, "message": f"{field_name} must be a number"})
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        details.append({"field": field_name, "message": f"{field_name} must be a number"})
        return None


def _normalize_timestamp(value: Any, details: list[dict[str, Any]]) -> str | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            details.append({"field": "timestamp", "message": "timestamp cannot be empty"})
            return None
        try:
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except ValueError:
            details.append({"field": "timestamp", "message": "timestamp must be ISO-8601 or unix seconds"})
            return None

    details.append({"field": "timestamp", "message": "timestamp must be ISO-8601 or unix seconds"})
    return None
