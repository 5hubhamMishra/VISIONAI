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
from visionai.capabilities.browser import (
    BrowserOpener,
    browser_handlers,
    browser_manifests,
    default_browser_opener,
)
from visionai.capabilities.media import (
    KeyPresser,
    default_key_presser,
    media_handlers,
    media_manifests,
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


def build_runtime(
    *,
    launcher: Launcher = default_launcher,
    browser_opener: BrowserOpener = default_browser_opener,
    key_presser: KeyPresser = default_key_presser,
) -> Runtime:
    """Build the local runtime with the currently trusted built-in capabilities.

    `launcher`, `browser_opener`, and `key_presser` are injectable so
    tests can verify dispatch end to end through the real policy and
    dispatcher path without spawning a real process, browser, or media
    keypress.
    """

    manifests = (
        *system_info_manifests(),
        app_open_manifest(),
        *browser_manifests(),
        *media_manifests(),
        *meta_manifests(),
    )
    registry = CapabilityRegistry(manifests)
    audit = InMemoryAuditSink()
    policy = PolicyEngine(registry, FixedWindowRateLimiter())
    handlers = {
        **system_info_handlers(lambda: datetime.now().astimezone()),
        "app.open": make_app_open_handler(launcher),
        **browser_handlers(browser_opener),
        **media_handlers(key_presser),
        **meta_handlers(registry),
    }
    dispatcher = SerializedDispatcher(
        registry=registry,
        policy=policy,
        audit=audit,
        handlers=handlers,
    )
    return Runtime(registry=registry, audit=audit, dispatcher=dispatcher)
