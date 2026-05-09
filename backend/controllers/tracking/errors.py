from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TrackingError(Exception):
    code: str
    message: str
    status_code: int
    details: list[dict[str, Any]] = field(default_factory=list)

    def to_response(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "error": {
                "code": self.code,
                "message": self.message,
            }
        }
        if self.details:
            payload["error"]["details"] = self.details
        return payload


class ValidationError(TrackingError):
    def __init__(self, message: str, details: list[dict[str, Any]]) -> None:
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            status_code=400,
            details=details,
        )


class UnauthorizedError(TrackingError):
    def __init__(self, message: str = "Signature check failed") -> None:
        super().__init__(
            code="UNAUTHORIZED",
            message=message,
            status_code=401,
        )


class RepositoryError(TrackingError):
    def __init__(self, message: str = "Tracker repository call failed") -> None:
        super().__init__(
            code="REPOSITORY_ERROR",
            message=message,
            status_code=500,
        )
