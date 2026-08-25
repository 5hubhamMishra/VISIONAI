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
    from visionai.policy.engine import PolicyContext, PolicyEngine

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

    def dispatch(self, request: ActionRequest, context: PolicyContext) -> ActionResult:
        decision = self._policy.evaluate(request, context)
        if not decision.allowed:
            self._audit.record(
                AuditEvent(
                    category="policy",
                    actor="system",
                    summary=decision.reason,
                    risk_level=request.risk_level,
                )
            )
            return ActionResult(request_id=request.id, success=False, message=decision.reason)

        manifest = self._registry.get(request.capability_id)
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
