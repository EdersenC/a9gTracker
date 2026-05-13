"""Mission runtime service implementation for MissionRuntimeAPI."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Mapping, Protocol

from .failsafe_policy import FailsafeDecision, FailsafeEventV1, FailsafePolicy, FailsafeEventType
from .state_machine import (
    InvalidTransitionError,
    MissionStateMachine,
    RuntimeAction,
    RuntimeEvent,
    RuntimeState,
)


class VehiclePortV1(Protocol):
    async def connect(self) -> None: ...

    async def arm(self) -> None: ...

    async def set_mode(self, mode: str) -> None: ...

    async def upload_mission(self, plan: Any) -> None: ...

    async def start_mission(self) -> None: ...

    async def goto_home(self) -> None: ...

    async def hold(self) -> None: ...

    async def abort(self, reason: str) -> None: ...

    async def disconnect(self) -> None: ...


@dataclass(frozen=True)
class RuntimeEventRecord:
    kind: str
    state: RuntimeState
    reason_code: str
    data: Mapping[str, Any] = field(default_factory=dict)
    monotonic_ts_ms: int = field(default_factory=lambda: int(time.monotonic() * 1000))


class MissionRuntimeService:
    """Concrete MissionRuntimeAPI service with deterministic failsafe transitions."""

    def __init__(self, vehicle_port: VehiclePortV1, failsafe_policy: FailsafePolicy | None = None) -> None:
        self._vehicle = vehicle_port
        self._policy = failsafe_policy or FailsafePolicy()
        self._machine = MissionStateMachine()
        self._events: asyncio.Queue[RuntimeEventRecord] = asyncio.Queue()
        self._plan: Any | None = None
        self._active_failsafe_types: set[FailsafeEventType] = set()
        self._telemetry_unsubscribe: Callable[[], None] | None = None

    async def start(self, plan: Any) -> RuntimeState:
        if self._machine.state != RuntimeState.IDLE:
            raise RuntimeError(f"Mission runtime can only start from IDLE, got {self._machine.state.value}")

        self._plan = plan
        self._active_failsafe_types.clear()

        await self._apply_transition(RuntimeEvent.START)
        await self._vehicle.connect()
        self._bind_telemetry()

        try:
            await self._vehicle.upload_mission(plan)
            await self._vehicle.set_mode("MISSION")
            await self._vehicle.arm()
            await self._apply_transition(RuntimeEvent.PRECHECK_PASSED)
            await self._vehicle.start_mission()
            await self._apply_transition(RuntimeEvent.MISSION_STARTED)
            return self._machine.state
        except Exception:
            await self._apply_transition(RuntimeEvent.VEHICLE_ERROR, reason_code="STARTUP_FAILURE")
            raise

    async def stop(self) -> RuntimeState:
        if self._machine.state in {RuntimeState.IDLE, RuntimeState.COMPLETED, RuntimeState.ABORTED, RuntimeState.FAILED}:
            return self._machine.state

        try:
            await self._apply_transition(RuntimeEvent.STOP_REQUESTED)
            return self._machine.state
        except InvalidTransitionError:
            # Keep stop idempotent across intermediate states.
            return self._machine.state

    async def abort(self, reason: str) -> RuntimeState:
        failsafe = self._policy.mission_abort_event(reason)
        await self._emit_failsafe_event(failsafe)
        await self._apply_failsafe_decision(self._policy.decision_for(failsafe))
        return self._machine.state

    def get_state(self) -> RuntimeState:
        return self._machine.state

    async def complete_mission(self) -> RuntimeState:
        await self._apply_transition(RuntimeEvent.MISSION_COMPLETED)
        return self._machine.state

    async def event_stream(self) -> AsyncIterator[RuntimeEventRecord]:
        while True:
            event = await self._events.get()
            yield event

    async def ingest_telemetry(self, frame: Any) -> None:
        if self._machine.state not in {RuntimeState.PRECHECK, RuntimeState.ARMED, RuntimeState.ENROUTE, RuntimeState.HOLD, RuntimeState.RTH}:
            return

        for failsafe in self._policy.evaluate_telemetry(frame=frame, plan=self._plan):
            if failsafe.event_type in self._active_failsafe_types:
                continue
            self._active_failsafe_types.add(failsafe.event_type)
            await self._emit_failsafe_event(failsafe)
            await self._apply_failsafe_decision(self._policy.decision_for(failsafe))

    async def _apply_failsafe_decision(self, decision: FailsafeDecision) -> None:
        await self._apply_transition(decision.runtime_event, reason_code=decision.reason_code)

    async def _apply_transition(self, event: RuntimeEvent, reason_code: str | None = None) -> None:
        transition = self._machine.transition(event, reason_code=reason_code)
        await self._emit_runtime_transition(transition.state, transition.reason_code)
        await self._invoke_action(transition.action, transition.reason_code)

    async def _invoke_action(self, action: RuntimeAction, reason_code: str) -> None:
        if action == RuntimeAction.NONE:
            return
        if action == RuntimeAction.HOLD:
            await self._vehicle.hold()
            return
        if action == RuntimeAction.GOTO_HOME:
            await self._vehicle.goto_home()
            return
        if action == RuntimeAction.ABORT:
            await self._vehicle.abort(reason_code)
            await self._vehicle.disconnect()
            self._unbind_telemetry()
            return
        if action == RuntimeAction.DISCONNECT:
            await self._vehicle.disconnect()
            self._unbind_telemetry()
            return

    async def _emit_runtime_transition(self, state: RuntimeState, reason_code: str) -> None:
        await self._events.put(
            RuntimeEventRecord(
                kind="STATE_TRANSITION",
                state=state,
                reason_code=reason_code,
            )
        )

    async def _emit_failsafe_event(self, event: FailsafeEventV1) -> None:
        await self._events.put(
            RuntimeEventRecord(
                kind="FAILSAFE_EVENT",
                state=self._machine.state,
                reason_code=event.reason_code,
                data={
                    "event_type": event.event_type.value,
                    "severity": event.severity.value,
                    "source": event.source,
                    "metadata": dict(event.metadata),
                },
            )
        )

    def _bind_telemetry(self) -> None:
        callback = self._telemetry_callback

        if hasattr(self._vehicle, "subscribe"):
            maybe_unsub = self._vehicle.subscribe(callback)  # type: ignore[attr-defined]
            if callable(maybe_unsub):
                self._telemetry_unsubscribe = maybe_unsub
            return

        telemetry_stream = getattr(self._vehicle, "telemetry", None)
        if telemetry_stream and hasattr(telemetry_stream, "subscribe"):
            maybe_unsub = telemetry_stream.subscribe(callback)
            if callable(maybe_unsub):
                self._telemetry_unsubscribe = maybe_unsub

    def _unbind_telemetry(self) -> None:
        if self._telemetry_unsubscribe is not None:
            self._telemetry_unsubscribe()
            self._telemetry_unsubscribe = None

    def _telemetry_callback(self, frame: Any) -> None:
        asyncio.create_task(self.ingest_telemetry(frame))
