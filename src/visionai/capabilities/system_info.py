"""Read-only system information capabilities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import psutil

from visionai.capabilities.dispatcher import CapabilityHandler
from visionai.capabilities.manifest import (
    CapabilityManifest,
    IdempotencyMode,
    ParameterSpec,
    ParameterType,
)
from visionai.core.events import ActionRequest, ActionResult, RiskLevel

Clock = Callable[[], datetime]


@dataclass(frozen=True)
class BatteryStatus:
    """A snapshot of the local battery, if one is present."""

    percent: float | None
    plugged_in: bool | None


@dataclass(frozen=True)
class HealthSnapshot:
    """A snapshot of basic system load."""

    cpu_percent: float
    memory_percent: float


BatteryProbe = Callable[[], BatteryStatus]
HealthProbe = Callable[[], HealthSnapshot]


def read_battery_status() -> BatteryStatus:
    """Read the current battery state, or report none present.

    Desktops and many VMs have no battery sensor at all, which is a normal
    condition, not a failure. Platforms without battery support raise
    NotImplementedError or OSError from psutil; both are treated the same.
    """
    try:
        battery = psutil.sensors_battery()
    except (NotImplementedError, OSError):
        return BatteryStatus(percent=None, plugged_in=None)
    if battery is None:
        return BatteryStatus(percent=None, plugged_in=None)
    return BatteryStatus(percent=round(battery.percent, 1), plugged_in=battery.power_plugged)


def read_health_snapshot() -> HealthSnapshot:
    """Read current CPU and memory utilisation as a percentage."""
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory_percent = psutil.virtual_memory().percent
    return HealthSnapshot(cpu_percent=cpu_percent, memory_percent=memory_percent)


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


def system_battery_manifest() -> CapabilityManifest:
    """Return the manifest for the battery-status capability."""

    return CapabilityManifest(
        id="system.battery",
        description="Return the current battery charge and power source, if present.",
        risk_level=RiskLevel.READ_ONLY,
        rate_limit_per_minute=30,
        timeout_seconds=2,
        idempotency=IdempotencyMode.IDEMPOTENT,
        audit_category="system.info",
        handler_id="system.battery",
    )


def system_health_manifest() -> CapabilityManifest:
    """Return the manifest for the basic system health capability."""

    return CapabilityManifest(
        id="system.health",
        description="Return current CPU and memory utilisation as a percentage.",
        risk_level=RiskLevel.READ_ONLY,
        rate_limit_per_minute=30,
        timeout_seconds=2,
        idempotency=IdempotencyMode.IDEMPOTENT,
        audit_category="system.info",
        handler_id="system.health",
    )


def system_info_manifests() -> tuple[CapabilityManifest, ...]:
    """Return all built-in read-only system information manifests."""

    return (
        system_time_manifest(),
        system_date_manifest(),
        system_battery_manifest(),
        system_health_manifest(),
    )


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


def make_system_battery_handler(battery_probe: BatteryProbe) -> CapabilityHandler:
    """Create a handler that reports current battery status."""

    def handle(request: ActionRequest) -> ActionResult:
        status = battery_probe()
        if status.percent is None:
            message = "No battery detected."
        else:
            power_source = "plugged in" if status.plugged_in else "on battery power"
            message = f"Battery is at {status.percent:.0f}% and {power_source}."
        return ActionResult(request_id=request.id, success=True, message=message)

    return handle


def make_system_health_handler(health_probe: HealthProbe) -> CapabilityHandler:
    """Create a handler that reports current CPU and memory utilisation."""

    def handle(request: ActionRequest) -> ActionResult:
        snapshot = health_probe()
        message = (
            f"CPU is at {snapshot.cpu_percent:.0f}% "
            f"and memory is at {snapshot.memory_percent:.0f}%."
        )
        return ActionResult(request_id=request.id, success=True, message=message)

    return handle


def system_info_handlers(
    clock: Clock,
    battery_probe: BatteryProbe = read_battery_status,
    health_probe: HealthProbe = read_health_snapshot,
) -> dict[str, CapabilityHandler]:
    """Return all built-in read-only system information handlers."""

    return {
        "system.time": make_system_time_handler(clock),
        "system.date": make_system_date_handler(clock),
        "system.battery": make_system_battery_handler(battery_probe),
        "system.health": make_system_health_handler(health_probe),
    }
