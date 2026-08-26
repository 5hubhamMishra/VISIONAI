"""Event-driven orchestration over the safe runtime.

The orchestrator is glue, not authority: it turns final transcript
events into a typed plan via `TextCommandPlanner`, publishes the intent
and plan for UI/audit consumers, and sends any executable step through
the existing policy/dispatcher boundary.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import replace
from uuid import UUID

from visionai.capabilities.dispatcher import SerializedDispatcher
from visionai.core.cancellation import OperationController
from visionai.core.errors import EventBusClosed, StateTransitionError, VisionAIError
from visionai.core.event_bus import EventBus
from visionai.core.events import (
    ActionRequest,
    ErrorEvent,
    EventBase,
    PermissionRequest,
    TranscriptEvent,
)
from visionai.core.state import AppState, StateMachine
from visionai.orchestration.text_planner import TextCommandPlanner
from visionai.policy import ConfirmationService, PolicyContext
from visionai.policy.permissions import JsonPermissionStore

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
        confirmation: ConfirmationService,
        permission_store: JsonPermissionStore | None = None,
        state_machine: StateMachine | None = None,
        policy_context_factory: PolicyContextFactory = PolicyContext,
    ) -> None:
        self._input_bus = input_bus
        self._output_bus = output_bus
        self._planner = planner
        self._dispatcher = dispatcher
        self._operations = operations
        self._confirmation = confirmation
        self._permission_store = permission_store
        self._state = state_machine or StateMachine()
        self._policy_context_factory = policy_context_factory
        self._pending_confirmations: dict[UUID, ActionRequest] = {}
        self._pending_permissions: dict[UUID, tuple[ActionRequest, str]] = {}

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

    async def confirm(self, confirmation_id: UUID) -> None:
        """Apply a previously issued confirmation and execute its request.

        Safe against replay, and against unknown or expired IDs:
        `ConfirmationService` binds each confirmation to the exact request
        it was created for, consumes it on first use, and rejects it once
        expired. If any of that fails, nothing executes and an `ErrorEvent`
        is published instead -- matching Section 9's "no effect on timeout"
        requirement.
        """

        request = self._pending_confirmations.pop(confirmation_id, None)
        if request is None:
            await self._publish_error("confirmation is missing or already used")
            return

        try:
            self._confirmation.validate(request, confirmation_id)
        except VisionAIError as exc:
            await self._publish_error(str(exc))
            self._try_transition(AppState.ERROR, reason=type(exc).__name__)
            self._state.cancel(reason="confirmation rejected")
            return

        context = self._policy_context_factory()
        confirmed_context = replace(
            context, confirmed_request_ids=context.confirmed_request_ids | {request.id}
        )
        await self._execute(request, confirmed_context)

    def cancel_pending_confirmation(self, confirmation_id: UUID) -> bool:
        """Discard a pending confirmation without executing it.

        Returns False for an unknown ID (already used, expired, or never
        issued) -- a no-op rather than an error, since a stale cancel
        request should have no effect either way.
        """

        removed = self._pending_confirmations.pop(confirmation_id, None) is not None
        self._confirmation.discard(confirmation_id)
        if removed and self._state.state is AppState.AWAITING_CONFIRMATION:
            self._state.cancel(reason="confirmation cancelled")
        return removed

    async def grant_permission(self, permission_id: UUID) -> None:
        """Grant a pending permission and continue policy-gated execution."""

        pending = self._pending_permissions.pop(permission_id, None)
        if pending is None:
            await self._publish_error("permission request is missing or already used")
            return
        if self._permission_store is None:
            await self._publish_error("permission store is not configured")
            self._try_transition(AppState.ERROR, reason="permission store missing")
            self._state.cancel(reason="permission rejected")
            return

        request, action_summary = pending
        self._permission_store.grant(request.capability_id)
        context = self._policy_context_factory()
        decision = self._dispatcher.evaluate(request, context)
        if decision.requires_permission:
            await self._publish_error("permission grant was not applied")
            self._try_transition(AppState.ERROR, reason="permission grant failed")
            self._state.cancel(reason="permission rejected")
            return
        if decision.requires_confirmation:
            await self._request_confirmation(request, action_summary)
            return

        await self._execute(request, context)

    def cancel_pending_permission(self, permission_id: UUID) -> bool:
        """Discard a pending permission request without granting or executing."""

        removed = self._pending_permissions.pop(permission_id, None) is not None
        if removed and self._state.state is AppState.AWAITING_PERMISSION:
            self._state.cancel(reason="permission cancelled")
        return removed

    def _discard_all_pending_confirmations(self) -> None:
        for confirmation_id in tuple(self._pending_confirmations):
            self.cancel_pending_confirmation(confirmation_id)

    def _discard_all_pending_permissions(self) -> None:
        for permission_id in tuple(self._pending_permissions):
            self.cancel_pending_permission(permission_id)

    async def _process_transcript(self, event: TranscriptEvent) -> None:
        if not event.is_final:
            return

        try:
            self._transition_to_interpreting()
            intent, plan = self._planner.plan(event.text)
            await self._publish(intent)
            await self._publish(plan)

            if not plan.steps:
                self._state.transition(AppState.RESPONDING, reason="no executable action")
                return

            request = plan.steps[0]
            context = self._policy_context_factory()
            decision = self._dispatcher.evaluate(request, context)
            if decision.requires_permission:
                await self._request_permission(request, plan.summary)
                return
            if decision.requires_confirmation:
                await self._request_confirmation(request, plan.summary)
                return

            await self._execute(request, context)
        except VisionAIError as exc:
            await self._publish_error(str(exc))
            self._try_transition(AppState.ERROR, reason=type(exc).__name__)
        finally:
            # Pending prompts must survive this turn -- everything else
            # always returns to IDLE, matching the pre-prompt behavior
            # where every turn was atomic.
            if self._state.state not in {
                AppState.AWAITING_PERMISSION,
                AppState.AWAITING_CONFIRMATION,
            }:
                self._state.cancel(reason="turn complete")

    async def _request_permission(self, request: ActionRequest, action_summary: str) -> None:
        permission = PermissionRequest(
            request_id=request.id,
            capability_id=request.capability_id,
            action_summary=action_summary,
            risk_level=request.risk_level,
        )
        self._pending_permissions[permission.id] = (request, action_summary)
        self._state.transition(AppState.AWAITING_PERMISSION, reason=request.capability_id)
        await self._publish(permission)

    async def _request_confirmation(self, request: ActionRequest, action_summary: str) -> None:
        confirmation = self._confirmation.create(request, action_summary=action_summary)
        self._pending_confirmations[confirmation.id] = request
        self._state.transition(AppState.AWAITING_CONFIRMATION, reason=request.capability_id)
        await self._publish(confirmation)

    async def _execute(self, request: ActionRequest, context: PolicyContext) -> None:
        token = None
        try:
            if request.capability_id != "system.stop":
                token = self._operations.begin_operation()
            self._state.transition(AppState.EXECUTING, reason=request.capability_id)
            result = self._dispatcher.dispatch(request, context)
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
        if self._state.state in {AppState.AWAITING_PERMISSION, AppState.AWAITING_CONFIRMATION}:
            self._discard_all_pending_permissions()
            self._discard_all_pending_confirmations()
            if self._state.state in {AppState.AWAITING_PERMISSION, AppState.AWAITING_CONFIRMATION}:
                self._state.cancel(reason="superseded by a new command")
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
