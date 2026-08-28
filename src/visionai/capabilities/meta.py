"""Meta capabilities: help, capability listing, and audit history control.

Covers Section 13's initial safe capabilities (help, capability listing,
stopping the current operation) plus `system.clear_history`, the first
real Risk 2 (Sensitive) capability -- Section 9 explicitly classifies
"history" as sensitive, so this is deliberately gated by both permission
and confirmation rather than running immediately like the Risk 0/1
capabilities above it, closing Section 15's "history deletion" mandatory
control.
"""

from __future__ import annotations

from visionai.capabilities.dispatcher import CapabilityHandler
from visionai.capabilities.manifest import CapabilityManifest, IdempotencyMode
from visionai.capabilities.registry import CapabilityRegistry
from visionai.core.cancellation import CancellationToken, OperationController
from visionai.core.events import ActionRequest, ActionResult, RiskLevel
from visionai.observability import InMemoryAuditSink


def system_capabilities_manifest() -> CapabilityManifest:
    """Return the manifest for the capability-listing meta-capability."""

    return CapabilityManifest(
        id="system.capabilities",
        description="List every capability currently registered.",
        risk_level=RiskLevel.READ_ONLY,
        rate_limit_per_minute=30,
        timeout_seconds=2,
        idempotency=IdempotencyMode.IDEMPOTENT,
        audit_category="system.info",
        handler_id="system.capabilities",
    )


def system_help_manifest() -> CapabilityManifest:
    """Return the manifest for the help meta-capability."""

    return CapabilityManifest(
        id="system.help",
        description="Explain what VisionAI can currently do.",
        risk_level=RiskLevel.READ_ONLY,
        rate_limit_per_minute=30,
        timeout_seconds=2,
        idempotency=IdempotencyMode.IDEMPOTENT,
        audit_category="system.info",
        handler_id="system.help",
    )


def system_stop_manifest() -> CapabilityManifest:
    """Return the manifest for stopping the current operation."""

    return CapabilityManifest(
        id="system.stop",
        description="Request cancellation of the current operation.",
        risk_level=RiskLevel.READ_ONLY,
        rate_limit_per_minute=60,
        timeout_seconds=1,
        idempotency=IdempotencyMode.IDEMPOTENT,
        audit_category="system.control",
        handler_id="system.stop",
    )


def system_clear_history_manifest() -> CapabilityManifest:
    """Return the manifest for clearing local audit history.

    Risk 2 (Sensitive) per Section 9's explicit classification of
    "history" -- requires both a granted permission and a fresh
    confirmation before it can run, unlike the Risk 0/1 capabilities
    above it in this module.
    """

    return CapabilityManifest(
        id="system.clear_history",
        description="Clear the local audit history.",
        risk_level=RiskLevel.SENSITIVE,
        permission_required=True,
        confirmation_required=True,
        rate_limit_per_minute=10,
        timeout_seconds=2,
        idempotency=IdempotencyMode.IDEMPOTENT,
        audit_category="system.history",
        handler_id="system.clear_history",
    )


def meta_manifests() -> tuple[CapabilityManifest, ...]:
    """Return all built-in meta-capability manifests."""

    return (
        system_capabilities_manifest(),
        system_help_manifest(),
        system_stop_manifest(),
        system_clear_history_manifest(),
    )


def make_system_stop_handler(controller: OperationController) -> CapabilityHandler:
    """Create a handler that requests cooperative cancellation."""

    def handle(request: ActionRequest, cancellation: CancellationToken) -> ActionResult:
        if controller.cancel_active_operation():
            message = "Stop requested."
        else:
            message = "No operation is currently running."
        return ActionResult(request_id=request.id, success=True, message=message)

    return handle


def make_system_capabilities_handler(registry: CapabilityRegistry) -> CapabilityHandler:
    """Create a handler that lists every capability registered in `registry`."""

    def handle(request: ActionRequest, cancellation: CancellationToken) -> ActionResult:
        manifests = sorted(registry.list(), key=lambda manifest: manifest.id)
        if not manifests:
            return ActionResult(
                request_id=request.id, success=True, message="No capabilities are registered."
            )
        lines = [f"{manifest.id}: {manifest.description}" for manifest in manifests]
        message = "Available capabilities:\n" + "\n".join(lines)
        return ActionResult(request_id=request.id, success=True, message=message)

    return handle


def make_system_help_handler(registry: CapabilityRegistry) -> CapabilityHandler:
    """Create a handler that summarizes current functionality."""

    def handle(request: ActionRequest, cancellation: CancellationToken) -> ActionResult:
        count = len(registry.list())
        message = (
            f"VisionAI is in early development with {count} capabilities registered. "
            "Run system.capabilities to list them by name. Gesture commands: open palm "
            "stops, thumbs up opens Notepad, peace sign shows help, index finger tells "
            "the time, and two fingers plus thumb raises volume. Closed fist starts "
            "voice mode when microphone capture is connected."
        )
        return ActionResult(request_id=request.id, success=True, message=message)

    return handle


def make_system_clear_history_handler(audit: InMemoryAuditSink) -> CapabilityHandler:
    """Create a handler that clears `audit`'s history.

    The dispatcher records its own audit entry for this call immediately
    after the handler returns (the same as every other capability), so
    "history was cleared, and when" is itself preserved -- clearing
    history does not erase evidence that a clear happened.
    """

    def handle(request: ActionRequest, cancellation: CancellationToken) -> ActionResult:
        audit.clear()
        return ActionResult(request_id=request.id, success=True, message="Audit history cleared.")

    return handle


def meta_handlers(
    registry: CapabilityRegistry,
    operation_controller: OperationController,
    audit: InMemoryAuditSink,
) -> dict[str, CapabilityHandler]:
    """Return all built-in meta-capability handlers, bound to `registry`."""

    return {
        "system.capabilities": make_system_capabilities_handler(registry),
        "system.help": make_system_help_handler(registry),
        "system.stop": make_system_stop_handler(operation_controller),
        "system.clear_history": make_system_clear_history_handler(audit),
    }
