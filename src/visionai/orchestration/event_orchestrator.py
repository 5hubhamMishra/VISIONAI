"""Event-driven orchestration over the safe runtime.

The orchestrator is glue, not authority: it turns final transcript
events into a typed plan via `TextCommandPlanner`, publishes the intent
and plan for UI/audit consumers, and sends any executable step through
the existing policy/dispatcher boundary.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress

from visionai.capabilities.dispatcher import SerializedDispatcher
from visionai.core.cancellation import OperationController
from visionai.core.errors import EventBusClosed, StateTransitionError, VisionAIError
from visionai.core.event_bus import EventBus
from visionai.core.events import ErrorEvent, EventBase, TranscriptEvent
from visionai.core.state import AppState, StateMachine
from visionai.orchestration.text_planner import TextCommandPlanner
from visionai.policy import PolicyContext

PolicyContextFactory = Callable[[], PolicyContext]


class EventOrchestrator:
    """Consume input events and publish planned/dispatch results."""

    def __init__(
        self,
        *,
        input_bus: EventBus,
        output_bus: EventBus,
        planner: TextCommandPlanner,
        dispatcher: SerializedDispatcher,
        operations: OperationController,
        state_machine: StateMachine | None = None,
        policy_context_factory: PolicyContextFactory = PolicyContext,
    ) -> None:
        self._input_bus = input_bus
        self._output_bus = output_bus
        self._planner = planner
        self._dispatcher = dispatcher
        self._operations = operations
        self._state = state_machine or StateMachine()
        self._policy_context_factory = policy_context_factory

    @property
    def state_machine(self) -> StateMachine:
        """Return the state machine used by this orchestrator."""

        return self._state

    async def run_until_closed(self) -> None:
        """Process input events until the input bus is closed."""

        async for event in self._input_bus.subscribe():
            await self.process_event(event)

    async def process_event(self, event: EventBase) -> None:
        """Process one event if this orchestrator understands it."""

        if isinstance(event, TranscriptEvent):
            await self._process_transcript(event)

    async def _process_transcript(self, event: TranscriptEvent) -> None:
        if not event.is_final:
            return

        token = None
        try:
            self._transition_to_interpreting()
            intent, plan = self._planner.plan(event.text)
            await self._publish(intent)
            await self._publish(plan)

            if not plan.steps:
                self._state.transition(AppState.RESPONDING, reason="no executable action")
                return

            request = plan.steps[0]
            if request.capability_id != "system.stop":
                token = self._operations.begin_operation()
            self._state.transition(AppState.EXECUTING, reason=request.capability_id)
            result = self._dispatcher.dispatch(request, self._policy_context_factory())
            await self._publish(result)
            self._state.transition(AppState.RESPONDING, reason="action result")
        except VisionAIError as exc:
            await self._publish_error(str(exc))
            self._try_transition(AppState.ERROR, reason=type(exc).__name__)
        finally:
            if token is not None:
                self._operations.finish_operation(token)
            self._state.cancel(reason="turn complete")

    def _transition_to_interpreting(self) -> None:
        if self._state.state is AppState.IDLE:
            self._state.transition(AppState.LISTENING, reason="transcript event")
        if self._state.state is AppState.LISTENING:
            self._state.transition(AppState.TRANSCRIBING, reason="final transcript")
        if self._state.state is AppState.TRANSCRIBING:
            self._state.transition(AppState.INTERPRETING, reason="plan text")

    async def _publish(self, event: EventBase) -> None:
        try:
            await self._output_bus.publish(event)
        except EventBusClosed:
            return

    async def _publish_error(self, message: str) -> None:
        await self._publish(
            ErrorEvent(error_type="orchestration", message=message, recoverable=True)
        )

    def _try_transition(self, state: AppState, *, reason: str) -> None:
        with suppress(StateTransitionError):
            self._state.transition(state, reason=reason)
