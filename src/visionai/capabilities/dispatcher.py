"""Serialized capability dispatcher."""

from __future__ import annotations

from collections.abc import Callable
from threading import Lock
from typing import TYPE_CHECKING

from visionai.capabilities.registry import CapabilityRegistry
from visionai.core.errors import DispatchError
from visionai.core.events import ActionRequest, ActionResult, AuditEvent
from visionai.observability.audit import InMemoryAuditSink

if TYPE_CHECKING:
    from visionai.policy.engine import PolicyContext, PolicyDecision, PolicyEngine

CapabilityHandler = Callable[[ActionRequest], ActionResult]


class SerializedDispatcher:
    """Executes registered handlers one at a time after policy approval."""

    def __init__(
        self,
        *,
        registry: CapabilityRegistry,
        policy: PolicyEngine,
        audit: InMemoryAuditSink,
        handlers: dict[str, CapabilityHandler] | None = None,
    ) -> None:
        self._registry = registry
        self._policy = policy
        self._audit = audit
        self._handlers = handlers or {}
        self._lock = Lock()

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

    def dispatch(self, request: ActionRequest, context: PolicyContext) -> ActionResult:
        # Looked up from the registry, not request.risk_level: the caller
        # supplies that field, so trusting it for audit severity would let a
        # malicious or buggy request understate its true risk in the log.
        manifest = self._registry.get(request.capability_id)

        decision = self._policy.evaluate(request, context)
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

        with self._lock:
            result = handler(request)

        self._audit.record(
            AuditEvent(
                category=manifest.audit_category,
                actor="system",
                summary=result.message,
                risk_level=manifest.risk_level,
            )
        )
        return result
