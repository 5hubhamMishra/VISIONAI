"""Meta capabilities: help and capability listing.

These cover Section 13's initial safe capabilities: help, capability
listing, and stopping the current operation.
"""

from __future__ import annotations

from visionai.capabilities.dispatcher import CapabilityHandler
from visionai.capabilities.manifest import CapabilityManifest, IdempotencyMode
from visionai.capabilities.registry import CapabilityRegistry
from visionai.core.cancellation import OperationController
from visionai.core.events import ActionRequest, ActionResult, RiskLevel


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


def meta_manifests() -> tuple[CapabilityManifest, ...]:
    """Return all built-in meta-capability manifests."""

    return (system_capabilities_manifest(), system_help_manifest(), system_stop_manifest())


def make_system_stop_handler(controller: OperationController) -> CapabilityHandler:
    """Create a handler that requests cooperative cancellation."""

    def handle(request: ActionRequest) -> ActionResult:
        if controller.cancel_active_operation():
            message = "Stop requested."
        else:
            message = "No operation is currently running."
        return ActionResult(request_id=request.id, success=True, message=message)

    return handle


def make_system_capabilities_handler(registry: CapabilityRegistry) -> CapabilityHandler:
    """Create a handler that lists every capability registered in `registry`."""

    def handle(request: ActionRequest) -> ActionResult:
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

    def handle(request: ActionRequest) -> ActionResult:
        count = len(registry.list())
        message = (
            f"VisionAI is in early development with {count} capabilities registered. "
            "Run system.capabilities to list them by name. Voice and gesture input, "
            "and any capability beyond the listed policy-gated surface, are not "
            "available yet."
        )
        return ActionResult(request_id=request.id, success=True, message=message)

    return handle


def meta_handlers(
    registry: CapabilityRegistry,
    operation_controller: OperationController,
) -> dict[str, CapabilityHandler]:
    """Return all built-in meta-capability handlers, bound to `registry`."""

    return {
        "system.capabilities": make_system_capabilities_handler(registry),
        "system.help": make_system_help_handler(registry),
        "system.stop": make_system_stop_handler(operation_controller),
    }
