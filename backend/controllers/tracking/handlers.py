from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from backend.controllers.tracking.errors import RepositoryError, TrackingError, UnauthorizedError
from backend.controllers.tracking.validation import normalize_tracker_payload
from backend.realtime.broker import RealtimeBroker, Subscription


class TrackingController:
    def __init__(
        self,
        repository: Any,
        realtime_broker: RealtimeBroker,
        auth_hook: Callable[[Mapping[str, str], dict[str, Any]], bool] | None = None,
    ) -> None:
        self._repository = repository
        self._realtime_broker = realtime_broker
        self._auth_hook = auth_hook

    def ingest_position(
        self,
        *,
        payload: dict[str, Any],
        headers: Mapping[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        normalized = normalize_tracker_payload(payload)
        self._authorize(headers=headers or {}, payload=normalized)

        stored = self._persist_position(normalized)
        event_payload = _normalize_position_record(stored)
        self._realtime_broker.publish(event="tracking.position.updated", payload=event_payload)

        return 201, {"data": event_payload}

    def get_latest_positions(
        self,
        *,
        tracker_ids: list[str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        results = self._read_latest_positions(tracker_ids=tracker_ids)
        normalized = [_normalize_position_record(item) for item in results]
        return 200, {"data": normalized}

    def get_position_history(
        self,
        *,
        tracker_id: str,
        start: str | None = None,
        end: str | None = None,
        limit: int | None = None,
    ) -> tuple[int, dict[str, Any]]:
        results = self._read_position_history(
            tracker_id=tracker_id,
            start=start,
            end=end,
            limit=limit,
        )
        normalized = [_normalize_position_record(item) for item in results]
        return 200, {"data": normalized}

    def subscribe(self) -> Subscription:
        return self._realtime_broker.subscribe()

    def unsubscribe(self, subscription: Subscription) -> None:
        self._realtime_broker.unsubscribe(subscription)

    def _authorize(self, *, headers: Mapping[str, str], payload: dict[str, Any]) -> None:
        if not self._auth_hook:
            return
        is_valid = self._auth_hook(headers, payload)
        if not is_valid:
            raise UnauthorizedError()

    def _persist_position(self, payload: dict[str, Any]) -> dict[str, Any]:
        method_names = (
            "save_position",
            "create_position",
            "insert_position",
            "add_position",
            "persist_position",
        )
        for name in method_names:
            method = getattr(self._repository, name, None)
            if callable(method):
                try:
                    result = method(payload)
                    return payload if result is None else result
                except Exception as exc:  # noqa: BLE001
                    raise RepositoryError(str(exc)) from exc
        raise RepositoryError("Repository missing position write method")

    def _read_latest_positions(self, *, tracker_ids: list[str] | None) -> list[dict[str, Any]]:
        method_names = (
            "list_latest_positions",
            "get_latest_positions",
            "fetch_latest_positions",
        )
        for name in method_names:
            method = getattr(self._repository, name, None)
            if callable(method):
                try:
                    items = method(tracker_ids=tracker_ids)
                    return list(items or [])
                except TypeError:
                    items = method(tracker_ids)
                    return list(items or [])
                except Exception as exc:  # noqa: BLE001
                    raise RepositoryError(str(exc)) from exc
        raise RepositoryError("Repository missing latest positions read method")

    def _read_position_history(
        self,
        *,
        tracker_id: str,
        start: str | None,
        end: str | None,
        limit: int | None,
    ) -> list[dict[str, Any]]:
        method_names = (
            "list_position_history",
            "get_position_history",
            "fetch_position_history",
        )
        for name in method_names:
            method = getattr(self._repository, name, None)
            if callable(method):
                try:
                    items = method(
                        tracker_id=tracker_id,
                        start=start,
                        end=end,
                        limit=limit,
                    )
                    return list(items or [])
                except TypeError:
                    items = method(tracker_id, start, end, limit)
                    return list(items or [])
                except Exception as exc:  # noqa: BLE001
                    raise RepositoryError(str(exc)) from exc
        raise RepositoryError("Repository missing history read method")


def _normalize_position_record(raw: dict[str, Any]) -> dict[str, Any]:
    data = dict(raw)
    if "tracker_id" in data and "trackerId" not in data:
        data["trackerId"] = data.pop("tracker_id")
    if "latitude" in data and "lat" not in data:
        data["lat"] = data.pop("latitude")
    if "longitude" in data and "lon" not in data:
        data["lon"] = data.pop("longitude")

    timestamp = data.get("timestamp") or data.get("createdAt")
    if isinstance(timestamp, datetime):
        data["timestamp"] = timestamp.isoformat().replace("+00:00", "Z")

    # Keep canonical response shape regardless of repository column naming.
    canonical: dict[str, Any] = {
        "trackerId": data.get("trackerId"),
        "timestamp": data.get("timestamp"),
        "lat": _optional_float(data.get("lat")),
        "lon": _optional_float(data.get("lon")),
    }
    for field_name in ("speed", "heading", "accuracy"):
        if field_name in data and data[field_name] is not None:
            canonical[field_name] = _optional_float(data[field_name])
    return canonical


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def handle_controller_error(exc: Exception) -> tuple[int, dict[str, Any]]:
    if isinstance(exc, TrackingError):
        return exc.status_code, exc.to_response()
    error = RepositoryError()
    return error.status_code, error.to_response()
