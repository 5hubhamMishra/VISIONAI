"""Runtime assembly for safe built-in capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from visionai.capabilities import CapabilityRegistry, SerializedDispatcher
from visionai.capabilities.applications import (
    Launcher,
    app_open_manifest,
    default_launcher,
    make_app_open_handler,
)
from visionai.capabilities.meta import meta_handlers, meta_manifests
from visionai.capabilities.system_info import system_info_handlers, system_info_manifests
from visionai.observability import InMemoryAuditSink
from visionai.policy import FixedWindowRateLimiter, PolicyEngine


@dataclass(frozen=True, slots=True)
class Runtime:
    """Small runtime container for the verified dispatcher path."""

    registry: CapabilityRegistry
    audit: InMemoryAuditSink
    dispatcher: SerializedDispatcher


def build_runtime(*, launcher: Launcher = default_launcher) -> Runtime:
    """Build the local runtime with the currently trusted built-in capabilities.

    `launcher` is injectable so tests can verify app.open dispatch end to
    end through the real policy and dispatcher path without spawning a
    real process.
    """

    manifests = (*system_info_manifests(), app_open_manifest(), *meta_manifests())
    registry = CapabilityRegistry(manifests)
    audit = InMemoryAuditSink()
    policy = PolicyEngine(registry, FixedWindowRateLimiter())
    handlers = {
        **system_info_handlers(lambda: datetime.now().astimezone()),
        "app.open": make_app_open_handler(launcher),
        **meta_handlers(registry),
    }
    dispatcher = SerializedDispatcher(
        registry=registry,
        policy=policy,
        audit=audit,
        handlers=handlers,
    )
    return Runtime(registry=registry, audit=audit, dispatcher=dispatcher)
