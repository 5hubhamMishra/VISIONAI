"""The application state machine.

Every user-facing interaction moves through this state machine so the UI,
audit log, and policy engine always agree on what VisionAI is currently
doing. Transitions are explicit and validated; anything not listed in
`_TRANSITIONS` is rejected rather than allowed by omission.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from time import monotonic

from visionai.core.errors import StateTransitionError


class AppState(Enum):
    IDLE = auto()
    LISTENING = auto()
    TRANSCRIBING = auto()
    INTERPRETING = auto()
    AWAITING_CLARIFICATION = auto()
    AWAITING_CONFIRMATION = auto()
    EXECUTING = auto()
    RESPONDING = auto()
    ERROR = auto()
    STOPPED = auto()


# Explicit allow-list of valid transitions. STOPPED is terminal.
_TRANSITIONS: dict[AppState, frozenset[AppState]] = {
    AppState.IDLE: frozenset({AppState.LISTENING, AppState.STOPPED}),
    AppState.LISTENING: frozenset(
        {AppState.TRANSCRIBING, AppState.IDLE, AppState.ERROR, AppState.STOPPED}
    ),
    AppState.TRANSCRIBING: frozenset(
        {AppState.INTERPRETING, AppState.IDLE, AppState.ERROR, AppState.STOPPED}
    ),
    AppState.INTERPRETING: frozenset(
        {
            AppState.AWAITING_CLARIFICATION,
            AppState.AWAITING_CONFIRMATION,
            AppState.EXECUTING,
            AppState.RESPONDING,
            AppState.IDLE,
            AppState.ERROR,
            AppState.STOPPED,
        }
    ),
    AppState.AWAITING_CLARIFICATION: frozenset(
        {AppState.INTERPRETING, AppState.IDLE, AppState.ERROR, AppState.STOPPED}
    ),
    AppState.AWAITING_CONFIRMATION: frozenset(
        {AppState.EXECUTING, AppState.IDLE, AppState.ERROR, AppState.STOPPED}
    ),
    AppState.EXECUTING: frozenset({AppState.RESPONDING, AppState.ERROR, AppState.STOPPED}),
    AppState.RESPONDING: frozenset({AppState.IDLE, AppState.ERROR, AppState.STOPPED}),
    AppState.ERROR: frozenset({AppState.IDLE, AppState.STOPPED}),
    AppState.STOPPED: frozenset(),
}

# States a user or the system can cancel out of, back to IDLE.
CANCELLABLE_STATES: frozenset[AppState] = frozenset(_TRANSITIONS) - {
    AppState.IDLE,
    AppState.STOPPED,
}


@dataclass(frozen=True)
class Transition:
    """A single recorded state change, for audit and testing."""

    from_state: AppState
    to_state: AppState
    timestamp: float
    reason: str | None = None


@dataclass
class StateMachine:
    """Owns the current `AppState` and enforces valid transitions."""

    state: AppState = AppState.IDLE
    history: list[Transition] = field(default_factory=list)
    _listeners: list[Callable[[Transition], None]] = field(default_factory=list)

    def can_transition(self, to_state: AppState) -> bool:
        return to_state in _TRANSITIONS[self.state]

    def transition(self, to_state: AppState, *, reason: str | None = None) -> Transition:
        """Move to `to_state`, raising `StateTransitionError` if disallowed."""
        if not self.can_transition(to_state):
            raise StateTransitionError(
                f"Cannot transition from {self.state.name} to {to_state.name}"
            )
        record = Transition(
            from_state=self.state, to_state=to_state, timestamp=monotonic(), reason=reason
        )
        self.state = to_state
        self.history.append(record)
        for listener in self._listeners:
            listener(record)
        return record

    def cancel(self, *, reason: str = "cancelled") -> Transition | None:
        """Cancel the current operation back to IDLE, if cancellable.

        Returns None (a no-op) if already IDLE or STOPPED, since there is
        nothing in progress to cancel.
        """
        if self.state not in CANCELLABLE_STATES:
            return None
        return self.transition(AppState.IDLE, reason=reason)

    def on_transition(self, listener: Callable[[Transition], None]) -> None:
        """Register a callback invoked after every successful transition."""
        self._listeners.append(listener)
