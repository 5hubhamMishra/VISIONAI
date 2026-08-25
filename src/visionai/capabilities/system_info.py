"""Read-only system information capabilities."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from visionai.capabilities.dispatcher import CapabilityHandler
from visionai.capabilities.manifest import (
    CapabilityManifest,
    IdempotencyMode,
    ParameterSpec,
    ParameterType,
)
from visionai.core.events import ActionRequest, ActionResult, RiskLevel

Clock = Callable[[], datetime]


def system_time_manifest() -> CapabilityManifest:
    """Return the manifest for the current-time capability."""

    return CapabilityManifest(
        id="system.time",
        description="Return the current local time.",
        parameters={
            "format": ParameterSpec(
                type=ParameterType.STRING,
                required=False,
                description="One of 24h, 12h, or iso.",
            )
        },
        risk_level=RiskLevel.READ_ONLY,
        rate_limit_per_minute=60,
        timeout_seconds=2,
        idempotency=IdempotencyMode.IDEMPOTENT,
        audit_category="system.info",
        handler_id="system.time",
    )


def system_date_manifest() -> CapabilityManifest:
    """Return the manifest for the current-date capability."""

    return CapabilityManifest(
        id="system.date",
        description="Return the current local date.",
        parameters={
            "format": ParameterSpec(
                type=ParameterType.STRING,
                required=False,
                description="One of long, short, or iso.",
            )
        },
        risk_level=RiskLevel.READ_ONLY,
        rate_limit_per_minute=60,
        timeout_seconds=2,
        idempotency=IdempotencyMode.IDEMPOTENT,
        audit_category="system.info",
        handler_id="system.date",
    )


def system_info_manifests() -> tuple[CapabilityManifest, ...]:
    """Return all built-in read-only system information manifests."""

    return (system_time_manifest(), system_date_manifest())


def make_system_time_handler(clock: Clock) -> CapabilityHandler:
    """Create a handler that formats the current local time."""

    def handle(request: ActionRequest) -> ActionResult:
        output_format = str(request.arguments.get("format", "24h"))
        now = clock()
        if output_format == "24h":
            message = f"It is {now:%H:%M:%S}."
        elif output_format == "12h":
            message = f"It is {now:%I:%M:%S %p}."
        elif output_format == "iso":
            message = f"It is {now.isoformat()}."
        else:
            return ActionResult(
                request_id=request.id,
                success=False,
                message="Unsupported time format.",
            )
        return ActionResult(request_id=request.id, success=True, message=message)

    return handle


def make_system_date_handler(clock: Clock) -> CapabilityHandler:
    """Create a handler that formats the current local date."""

    def handle(request: ActionRequest) -> ActionResult:
        output_format = str(request.arguments.get("format", "long"))
        now = clock()
        if output_format == "long":
            message = f"Today is {now:%A, %B %d, %Y}."
        elif output_format == "short":
            message = f"Today is {now:%Y-%m-%d}."
        elif output_format == "iso":
            message = f"Today is {now.date().isoformat()}."
        else:
            return ActionResult(
                request_id=request.id,
                success=False,
                message="Unsupported date format.",
            )
        return ActionResult(request_id=request.id, success=True, message=message)

    return handle


def system_info_handlers(clock: Clock) -> dict[str, CapabilityHandler]:
    """Return all built-in read-only system information handlers."""

    return {
        "system.time": make_system_time_handler(clock),
        "system.date": make_system_date_handler(clock),
    }
