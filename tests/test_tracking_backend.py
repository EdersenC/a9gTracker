from __future__ import annotations

import unittest

from backend.controllers.tracking.handlers import TrackingController
from backend.realtime.broker import RealtimeBroker
from backend.routes.tracking.router import TrackingRouter


class InMemoryTrackingRepository:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def save_position(self, payload: dict) -> dict:
        self.items.append(dict(payload))
        return dict(payload)

    def list_latest_positions(self, tracker_ids=None):
        latest: dict[str, dict] = {}
        for item in self.items:
            latest[item["trackerId"]] = item
        if tracker_ids:
            return [latest[key] for key in tracker_ids if key in latest]
        return list(latest.values())

    def list_position_history(self, tracker_id: str, start=None, end=None, limit=None):
        filtered = [item for item in self.items if item["trackerId"] == tracker_id]
        if limit is not None:
            return filtered[:limit]
        return filtered


class TrackingBackendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = InMemoryTrackingRepository()
        self.broker = RealtimeBroker()
        self.controller = TrackingController(repository=self.repo, realtime_broker=self.broker)
        self.router = TrackingRouter(self.controller)

    def test_ingest_persists_and_publishes(self) -> None:
        subscription = self.controller.subscribe()
        status, body = self.controller.ingest_position(
            payload={
                "trackerId": "car-01",
                "timestamp": "2026-05-09T00:00:00Z",
                "lat": 40.7128,
                "lon": -74.0060,
                "speed": 14.2,
            },
            headers={},
        )
        self.assertEqual(status, 201)
        self.assertEqual(len(self.repo.items), 1)
        event = next(subscription.iter_events(keepalive_seconds=0.1))
        self.assertIn("tracking.position.updated", event)
        self.assertIn('"trackerId":"car-01"', event)

    def test_invalid_payload_returns_contract_error(self) -> None:
        response = self.router.dispatch(
            method="POST",
            path="/tracking/positions",
            json_body={"trackerId": "", "lat": "north"},
        )
        self.assertEqual(response.status, 400)
        self.assertEqual(response.body["error"]["code"], "VALIDATION_ERROR")

    def test_latest_and_history_routes(self) -> None:
        self.controller.ingest_position(
            payload={"trackerId": "car-01", "timestamp": 1715212800, "lat": 10, "lon": 11},
            headers={},
        )
        self.controller.ingest_position(
            payload={"trackerId": "car-01", "timestamp": 1715212860, "lat": 12, "lon": 13},
            headers={},
        )
        latest = self.router.dispatch(method="GET", path="/tracking/latest")
        self.assertEqual(latest.status, 200)
        self.assertEqual(len(latest.body["data"]), 1)

        history = self.router.dispatch(
            method="GET", path="/tracking/history", query_string="trackerId=car-01&limit=1"
        )
        self.assertEqual(history.status, 200)
        self.assertEqual(len(history.body["data"]), 1)

    def test_auth_hook_failure(self) -> None:
        controller = TrackingController(
            repository=self.repo,
            realtime_broker=self.broker,
            auth_hook=lambda _headers, _payload: False,
        )
        router = TrackingRouter(controller)
        response = router.dispatch(
            method="POST",
            path="/tracking/positions",
            json_body={
                "trackerId": "car-02",
                "timestamp": "2026-05-09T00:00:00Z",
                "lat": 1,
                "lon": 2,
            },
        )
        self.assertEqual(response.status, 401)
        self.assertEqual(response.body["error"]["code"], "UNAUTHORIZED")


if __name__ == "__main__":
    unittest.main()
