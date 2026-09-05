"""Serialized capability dispatcher."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from threading import Lock
from typing import TYPE_CHECKING

from visionai.capabilities.registry import CapabilityRegistry
from visionai.core.cancellation import CancellationToken
from visionai.core.errors import DispatchError
from visionai.core.events import ActionRequest, ActionResult, AuditEvent
from visionai.observability.audit import InMemoryAuditSink

if TYPE_CHECKING:
    from visionai.policy.engine import PolicyContext, PolicyDecision, PolicyEngine

# The token is always real, never None -- callers that have no operation to
# track (e.g. the CLI's direct dispatch) get a fresh, never-cancelled one
# from dispatch() below, so a handler never needs a None-check to poll it.
CapabilityHandler = Callable[[ActionRequest, CancellationToken], ActionResult]


class SerializedDispatcher:
    """Executes registered handlers one at a time after policy approval."""

    def __init__(
        self,
        *,
        registry: CapabilityRegistry,
        policy: PolicyEngine,
        audit: InMemoryAuditSink,
        handlers: dict[str, CapabilityHandler] | None = None,
        policy_context_factory: Callable[[], PolicyContext] | None = None,
    ) -> None:
        self._registry = registry
        self._policy = policy
        self._audit = audit
        self._handlers = handlers or {}
        self._lock = Lock()
        self._policy_context_factory = policy_context_factory

    def register_handler(self, handler_id: str, handler: CapabilityHandler) -> None:
        if handler_id in self._handlers:
            raise DispatchError(f"handler already registered: {handler_id}")
        self._handlers[handler_id] = handler

    def evaluate(self, request: ActionRequest, context: PolicyContext) -> PolicyDecision:
        """Check policy without executing anything.

        Read-only: callers (e.g. the orchestrator, to decide whether to show
        a confirmation prompt) can inspect `requires_confirmation` here, but
        this cannot be used to bypass anything -- `dispatch()` always
        re-evaluates policy itself before running a handler, so policy stays
        the sole authority over execution regardless of what a caller does
        with this result.
        """

        return self._policy.evaluate(request, context, consume_rate_limit=False)

    def dispatch(
        self,
        request: ActionRequest,
        context: PolicyContext,
        *,
        cancellation: CancellationToken | None = None,
    ) -> ActionResult:
        # Looked up from the registry, not request.risk_level: the caller
        # supplies that field, so trusting it for audit severity would let a
        # malicious or buggy request understate its true risk in the log.
        manifest = self._registry.get(request.capability_id)

        decision = self._policy.evaluate(request, context, consume_rate_limit=False)
        if not decision.allowed:
            self._audit.record(
                AuditEvent(
                    category="policy",
                    actor="system",
                    summary=decision.reason,
                    risk_level=manifest.risk_level,
                )
            )
            return ActionResult(request_id=request.id, success=False, message=decision.reason)

        handler = self._handlers.get(manifest.handler_id)
        if handler is None:
            raise DispatchError(f"handler is not registered: {manifest.handler_id}")

        token = cancellation or CancellationToken()
        with self._lock:
            # Catches cancellation that landed while this request was
            # queued behind the lock -- a request cancelled before its
            # handler ever runs should never take effect. A handler that
            # is itself long-running receives the same token to poll
            # partway through, once one exists.
            if token.is_cancelled:
                result = ActionResult(
                    request_id=request.id,
                    success=False,
                    message="Operation was cancelled before it started.",
                )
            else:
                if self._policy_context_factory is not None:
                    # Waiting for another action must not preserve a revoked
                    # grant or an earlier unlocked-screen snapshot.
                    fresh = self._policy_context_factory()
                    context = replace(
                        context,
                        platform=fresh.platform,
                        locked_screen=context.locked_screen or fresh.locked_screen,
                        granted_capabilities=(
                            context.granted_capabilities & fresh.granted_capabilities
                        ),
                    )
                decision = self._policy.evaluate(request, context)
                result = (
                    handler(request, token)
                    if decision.allowed
                    else ActionResult(request_id=request.id, success=False, message=decision.reason)
                )

        self._audit.record(
            AuditEvent(
                category=manifest.audit_category,
                actor="system",
                summary=result.message,
                risk_level=manifest.risk_level,
            )
        )
        return result
