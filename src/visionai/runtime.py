"""Runtime assembly for safe built-in capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from visionai.capabilities import CapabilityRegistry, SerializedDispatcher
from visionai.capabilities.system_info import system_info_handlers, system_info_manifests
from visionai.observability import InMemoryAuditSink
from visionai.policy import FixedWindowRateLimiter, PolicyEngine


@dataclass(frozen=True, slots=True)
class Runtime:
    """Small runtime container for the verified dispatcher path."""

    registry: CapabilityRegistry
    audit: InMemoryAuditSink
    dispatcher: SerializedDispatcher


def build_runtime() -> Runtime:
    """Build the local runtime with only read-only built-in capabilities."""

    registry = CapabilityRegistry(system_info_manifests())
    audit = InMemoryAuditSink()
    policy = PolicyEngine(registry, FixedWindowRateLimiter())
    dispatcher = SerializedDispatcher(
        registry=registry,
        policy=policy,
        audit=audit,
        handlers=system_info_handlers(lambda: datetime.now().astimezone()),
    )
    return Runtime(registry=registry, audit=audit, dispatcher=dispatcher)
