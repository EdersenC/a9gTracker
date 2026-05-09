from __future__ import annotations

import json
from dataclasses import dataclass
from queue import Empty, Queue
from threading import Lock
from typing import Any, Iterator


@dataclass
class Subscription:
    queue: Queue[str]

    def iter_events(self, *, keepalive_seconds: float | None = 15.0) -> Iterator[str]:
        """Yield server-sent-event chunks for this subscription."""
        while True:
            try:
                chunk = self.queue.get(timeout=keepalive_seconds)
                yield chunk
            except Empty:
                yield ": keepalive\n\n"


class RealtimeBroker:
    """In-memory fan-out broker for realtime position updates."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._subscribers: set[Queue[str]] = set()

    def subscribe(self) -> Subscription:
        queue: Queue[str] = Queue()
        with self._lock:
            self._subscribers.add(queue)
        return Subscription(queue=queue)

    def unsubscribe(self, subscription: Subscription) -> None:
        with self._lock:
            self._subscribers.discard(subscription.queue)

    def publish(self, *, event: str, payload: dict[str, Any]) -> int:
        message = format_sse(event=event, payload=payload)
        with self._lock:
            subscribers = list(self._subscribers)
        for subscriber in subscribers:
            subscriber.put(message)
        return len(subscribers)


def format_sse(*, event: str, payload: dict[str, Any]) -> str:
    data = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return f"event: {event}\\ndata: {data}\\n\\n"
