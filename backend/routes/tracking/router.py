from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Mapping
from urllib.parse import parse_qs

from backend.controllers.tracking.handlers import TrackingController, handle_controller_error


@dataclass
class RouteResponse:
    status: int
    body: dict[str, Any] | None = None
    headers: dict[str, str] = field(default_factory=dict)
    stream: Iterator[str] | None = None


class TrackingRouter:
    """Transport-agnostic route mapper for tracking endpoints."""

    def __init__(self, controller: TrackingController) -> None:
        self._controller = controller

    def dispatch(
        self,
        *,
        method: str,
        path: str,
        query_string: str = "",
        headers: Mapping[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> RouteResponse:
        headers = headers or {}
        json_body = json_body or {}
        method = method.upper()

        try:
            if method == "POST" and path == "/tracking/positions":
                status, body = self._controller.ingest_position(payload=json_body, headers=headers)
                return RouteResponse(status=status, body=body)

            if method == "GET" and path == "/tracking/latest":
                query = parse_qs(query_string, keep_blank_values=False)
                tracker_ids = _split_csv_values(query.get("trackerId", []))
                status, body = self._controller.get_latest_positions(
                    tracker_ids=tracker_ids or None,
                )
                return RouteResponse(status=status, body=body)

            if method == "GET" and path == "/tracking/history":
                query = parse_qs(query_string, keep_blank_values=False)
                tracker_id = _first(query.get("trackerId"))
                if not tracker_id:
                    return RouteResponse(
                        status=400,
                        body={
                            "error": {
                                "code": "VALIDATION_ERROR",
                                "message": "trackerId is required",
                                "details": [{"field": "trackerId", "message": "Field is required"}],
                            }
                        },
                    )
                start = _first(query.get("start"))
                end = _first(query.get("end"))
                limit = _to_int(_first(query.get("limit")))
                status, body = self._controller.get_position_history(
                    tracker_id=tracker_id,
                    start=start,
                    end=end,
                    limit=limit,
                )
                return RouteResponse(status=status, body=body)

            if method == "GET" and path == "/tracking/stream":
                subscription = self._controller.subscribe()

                def _stream() -> Iterator[str]:
                    try:
                        for chunk in subscription.iter_events():
                            yield chunk
                    finally:
                        self._controller.unsubscribe(subscription)

                return RouteResponse(
                    status=200,
                    headers={
                        "Content-Type": "text/event-stream",
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                    },
                    stream=_stream(),
                )

            return RouteResponse(status=404, body={"error": {"code": "NOT_FOUND", "message": "Route not found"}})
        except Exception as exc:  # noqa: BLE001
            status, body = handle_controller_error(exc)
            return RouteResponse(status=status, body=body)


def build_tracking_routes(controller: TrackingController) -> TrackingRouter:
    return TrackingRouter(controller=controller)


def _split_csv_values(values: list[str]) -> list[str]:
    parsed: list[str] = []
    for value in values:
        for part in value.split(","):
            stripped = part.strip()
            if stripped:
                parsed.append(stripped)
    return parsed


def _first(values: list[str] | None) -> str | None:
    if not values:
        return None
    value = values[0].strip()
    return value or None


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None
