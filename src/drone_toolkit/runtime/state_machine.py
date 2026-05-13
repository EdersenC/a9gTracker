"""Mission runtime state machine and transition contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Tuple


class RuntimeState(str, Enum):
    IDLE = "IDLE"
    PRECHECK = "PRECHECK"
    ARMED = "ARMED"
    ENROUTE = "ENROUTE"
    RTH = "RTH"
    HOLD = "HOLD"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"
    FAILED = "FAILED"


class RuntimeEvent(str, Enum):
    START = "START"
    PRECHECK_PASSED = "PRECHECK_PASSED"
    MISSION_STARTED = "MISSION_STARTED"
    MISSION_COMPLETED = "MISSION_COMPLETED"
    STOP_REQUESTED = "STOP_REQUESTED"
    FAILSAFE_HOLD = "FAILSAFE_HOLD"
    FAILSAFE_RTH = "FAILSAFE_RTH"
    FAILSAFE_ABORT = "FAILSAFE_ABORT"
    VEHICLE_ERROR = "VEHICLE_ERROR"


class RuntimeAction(str, Enum):
    NONE = "NONE"
    HOLD = "HOLD"
    GOTO_HOME = "GOTO_HOME"
    ABORT = "ABORT"
    DISCONNECT = "DISCONNECT"


class InvalidTransitionError(RuntimeError):
    """Raised when an event is not legal for the current state."""


@dataclass(frozen=True)
class TransitionDecision:
    state: RuntimeState
    action: RuntimeAction
    reason_code: str


class MissionStateMachine:
    """Deterministic mission lifecycle transitions."""

    _TERMINAL_STATES = {
        RuntimeState.COMPLETED,
        RuntimeState.ABORTED,
        RuntimeState.FAILED,
    }

    _BASE_TRANSITIONS: Dict[Tuple[RuntimeState, RuntimeEvent], TransitionDecision] = {
        (RuntimeState.IDLE, RuntimeEvent.START): TransitionDecision(
            state=RuntimeState.PRECHECK,
            action=RuntimeAction.NONE,
            reason_code="START_REQUESTED",
        ),
        (RuntimeState.PRECHECK, RuntimeEvent.PRECHECK_PASSED): TransitionDecision(
            state=RuntimeState.ARMED,
            action=RuntimeAction.NONE,
            reason_code="PRECHECK_OK",
        ),
        (RuntimeState.ARMED, RuntimeEvent.MISSION_STARTED): TransitionDecision(
            state=RuntimeState.ENROUTE,
            action=RuntimeAction.NONE,
            reason_code="MISSION_EXECUTION_STARTED",
        ),
        (RuntimeState.ENROUTE, RuntimeEvent.MISSION_COMPLETED): TransitionDecision(
            state=RuntimeState.COMPLETED,
            action=RuntimeAction.DISCONNECT,
            reason_code="MISSION_COMPLETED",
        ),
        (RuntimeState.RTH, RuntimeEvent.MISSION_COMPLETED): TransitionDecision(
            state=RuntimeState.COMPLETED,
            action=RuntimeAction.DISCONNECT,
            reason_code="RTH_COMPLETED",
        ),
        (RuntimeState.ENROUTE, RuntimeEvent.STOP_REQUESTED): TransitionDecision(
            state=RuntimeState.HOLD,
            action=RuntimeAction.HOLD,
            reason_code="STOP_REQUESTED",
        ),
        (RuntimeState.ARMED, RuntimeEvent.STOP_REQUESTED): TransitionDecision(
            state=RuntimeState.HOLD,
            action=RuntimeAction.HOLD,
            reason_code="STOP_REQUESTED",
        ),
        (RuntimeState.PRECHECK, RuntimeEvent.STOP_REQUESTED): TransitionDecision(
            state=RuntimeState.HOLD,
            action=RuntimeAction.HOLD,
            reason_code="STOP_REQUESTED",
        ),
    }

    # RuntimeStateTransitionTableV1 mapping for failsafe events.
    _FAILSAFE_TRANSITIONS: Dict[Tuple[RuntimeState, RuntimeEvent], TransitionDecision] = {
        (RuntimeState.IDLE, RuntimeEvent.FAILSAFE_HOLD): TransitionDecision(
            state=RuntimeState.IDLE,
            action=RuntimeAction.NONE,
            reason_code="FAILSAFE_IGNORED_IDLE",
        ),
        (RuntimeState.PRECHECK, RuntimeEvent.FAILSAFE_HOLD): TransitionDecision(
            state=RuntimeState.HOLD,
            action=RuntimeAction.HOLD,
            reason_code="FAILSAFE_HOLD",
        ),
        (RuntimeState.ARMED, RuntimeEvent.FAILSAFE_HOLD): TransitionDecision(
            state=RuntimeState.HOLD,
            action=RuntimeAction.HOLD,
            reason_code="FAILSAFE_HOLD",
        ),
        (RuntimeState.ENROUTE, RuntimeEvent.FAILSAFE_HOLD): TransitionDecision(
            state=RuntimeState.HOLD,
            action=RuntimeAction.HOLD,
            reason_code="FAILSAFE_HOLD",
        ),
        (RuntimeState.RTH, RuntimeEvent.FAILSAFE_HOLD): TransitionDecision(
            state=RuntimeState.RTH,
            action=RuntimeAction.NONE,
            reason_code="FAILSAFE_ALREADY_RTH",
        ),
        (RuntimeState.HOLD, RuntimeEvent.FAILSAFE_HOLD): TransitionDecision(
            state=RuntimeState.HOLD,
            action=RuntimeAction.NONE,
            reason_code="FAILSAFE_ALREADY_HOLD",
        ),
        (RuntimeState.IDLE, RuntimeEvent.FAILSAFE_RTH): TransitionDecision(
            state=RuntimeState.IDLE,
            action=RuntimeAction.NONE,
            reason_code="FAILSAFE_IGNORED_IDLE",
        ),
        (RuntimeState.PRECHECK, RuntimeEvent.FAILSAFE_RTH): TransitionDecision(
            state=RuntimeState.RTH,
            action=RuntimeAction.GOTO_HOME,
            reason_code="FAILSAFE_RTH",
        ),
        (RuntimeState.ARMED, RuntimeEvent.FAILSAFE_RTH): TransitionDecision(
            state=RuntimeState.RTH,
            action=RuntimeAction.GOTO_HOME,
            reason_code="FAILSAFE_RTH",
        ),
        (RuntimeState.ENROUTE, RuntimeEvent.FAILSAFE_RTH): TransitionDecision(
            state=RuntimeState.RTH,
            action=RuntimeAction.GOTO_HOME,
            reason_code="FAILSAFE_RTH",
        ),
        (RuntimeState.RTH, RuntimeEvent.FAILSAFE_RTH): TransitionDecision(
            state=RuntimeState.RTH,
            action=RuntimeAction.NONE,
            reason_code="FAILSAFE_ALREADY_RTH",
        ),
        (RuntimeState.HOLD, RuntimeEvent.FAILSAFE_RTH): TransitionDecision(
            state=RuntimeState.RTH,
            action=RuntimeAction.GOTO_HOME,
            reason_code="FAILSAFE_RTH",
        ),
    }

    _ABORT_TRANSITIONS: Dict[Tuple[RuntimeState, RuntimeEvent], TransitionDecision] = {
        (RuntimeState.IDLE, RuntimeEvent.FAILSAFE_ABORT): TransitionDecision(
            state=RuntimeState.ABORTED,
            action=RuntimeAction.ABORT,
            reason_code="FAILSAFE_ABORT",
        ),
        (RuntimeState.PRECHECK, RuntimeEvent.FAILSAFE_ABORT): TransitionDecision(
            state=RuntimeState.ABORTED,
            action=RuntimeAction.ABORT,
            reason_code="FAILSAFE_ABORT",
        ),
        (RuntimeState.ARMED, RuntimeEvent.FAILSAFE_ABORT): TransitionDecision(
            state=RuntimeState.ABORTED,
            action=RuntimeAction.ABORT,
            reason_code="FAILSAFE_ABORT",
        ),
        (RuntimeState.ENROUTE, RuntimeEvent.FAILSAFE_ABORT): TransitionDecision(
            state=RuntimeState.ABORTED,
            action=RuntimeAction.ABORT,
            reason_code="FAILSAFE_ABORT",
        ),
        (RuntimeState.RTH, RuntimeEvent.FAILSAFE_ABORT): TransitionDecision(
            state=RuntimeState.ABORTED,
            action=RuntimeAction.ABORT,
            reason_code="FAILSAFE_ABORT",
        ),
        (RuntimeState.HOLD, RuntimeEvent.FAILSAFE_ABORT): TransitionDecision(
            state=RuntimeState.ABORTED,
            action=RuntimeAction.ABORT,
            reason_code="FAILSAFE_ABORT",
        ),
    }

    _VEHICLE_ERROR_TRANSITIONS: Dict[Tuple[RuntimeState, RuntimeEvent], TransitionDecision] = {
        (RuntimeState.IDLE, RuntimeEvent.VEHICLE_ERROR): TransitionDecision(
            state=RuntimeState.FAILED,
            action=RuntimeAction.ABORT,
            reason_code="VEHICLE_ERROR",
        ),
        (RuntimeState.PRECHECK, RuntimeEvent.VEHICLE_ERROR): TransitionDecision(
            state=RuntimeState.FAILED,
            action=RuntimeAction.ABORT,
            reason_code="VEHICLE_ERROR",
        ),
        (RuntimeState.ARMED, RuntimeEvent.VEHICLE_ERROR): TransitionDecision(
            state=RuntimeState.FAILED,
            action=RuntimeAction.ABORT,
            reason_code="VEHICLE_ERROR",
        ),
        (RuntimeState.ENROUTE, RuntimeEvent.VEHICLE_ERROR): TransitionDecision(
            state=RuntimeState.FAILED,
            action=RuntimeAction.ABORT,
            reason_code="VEHICLE_ERROR",
        ),
        (RuntimeState.RTH, RuntimeEvent.VEHICLE_ERROR): TransitionDecision(
            state=RuntimeState.FAILED,
            action=RuntimeAction.ABORT,
            reason_code="VEHICLE_ERROR",
        ),
        (RuntimeState.HOLD, RuntimeEvent.VEHICLE_ERROR): TransitionDecision(
            state=RuntimeState.FAILED,
            action=RuntimeAction.ABORT,
            reason_code="VEHICLE_ERROR",
        ),
    }

    def __init__(self) -> None:
        self._state = RuntimeState.IDLE
        self._transitions: Dict[Tuple[RuntimeState, RuntimeEvent], TransitionDecision] = {}
        self._transitions.update(self._BASE_TRANSITIONS)
        self._transitions.update(self._FAILSAFE_TRANSITIONS)
        self._transitions.update(self._ABORT_TRANSITIONS)
        self._transitions.update(self._VEHICLE_ERROR_TRANSITIONS)

    @property
    def state(self) -> RuntimeState:
        return self._state

    @property
    def is_terminal(self) -> bool:
        return self._state in self._TERMINAL_STATES

    def transition(self, event: RuntimeEvent, reason_code: str | None = None) -> TransitionDecision:
        if self.is_terminal:
            return TransitionDecision(
                state=self._state,
                action=RuntimeAction.NONE,
                reason_code=f"TERMINAL_{self._state.value}",
            )

        key = (self._state, event)
        if key not in self._transitions:
            raise InvalidTransitionError(
                f"Invalid runtime transition from {self._state.value} on {event.value}"
            )

        next_decision = self._transitions[key]
        self._state = next_decision.state
        if reason_code:
            return TransitionDecision(
                state=next_decision.state,
                action=next_decision.action,
                reason_code=reason_code,
            )
        return next_decision
