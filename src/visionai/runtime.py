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
from visionai.config.settings import get_settings
from visionai.core.cancellation import OperationController
from visionai.core.event_bus import EventBus
from visionai.core.state import StateMachine
from visionai.observability import InMemoryAuditSink
from visionai.orchestration import EventOrchestrator, InputAdapter, TextCommandPlanner
from visionai.orchestration.event_orchestrator import PolicyContextFactory
from visionai.platform.lock_state import LockStateAdapter, WindowsLockStateAdapter
from visionai.policy import ConfirmationService, FixedWindowRateLimiter, PolicyContext, PolicyEngine
from visionai.policy.permissions import JsonPermissionStore


@dataclass(frozen=True, slots=True)
class Runtime:
    """Small runtime container for the verified dispatcher path."""

    registry: CapabilityRegistry
    audit: InMemoryAuditSink
    dispatcher: SerializedDispatcher
    operations: OperationController
    planner: TextCommandPlanner
    confirmation: ConfirmationService
    permissions: JsonPermissionStore
    policy_context_factory: PolicyContextFactory
    input_bus: EventBus
    input_adapter: InputAdapter
    output_bus: EventBus
    orchestrator: EventOrchestrator
    state_machine: StateMachine


def build_runtime(
    *,
    launcher: Launcher = default_launcher,
    browser_opener: BrowserOpener = default_browser_opener,
    key_presser: KeyPresser = default_key_presser,
    operation_controller: OperationController | None = None,
    confirmation: ConfirmationService | None = None,
    lock_state: LockStateAdapter | None = None,
    permission_store: JsonPermissionStore | None = None,
    input_bus: EventBus | None = None,
    output_bus: EventBus | None = None,
    state_machine: StateMachine | None = None,
) -> Runtime:
    """Build the local runtime with the currently trusted built-in capabilities.

    `launcher`, `browser_opener`, and `key_presser` are injectable so
    tests can verify dispatch end to end through the real policy and
    dispatcher path without spawning a real process, browser, or media
    keypress.

    `lock_state` defaults to the real `WindowsLockStateAdapter`, and
    `permission_store` defaults to a `JsonPermissionStore` under
    `get_settings().data_dir`; both are checked fresh on every dispatch
    via `policy_context_factory`. Both the CLI (`app.py`) and the
    UI/orchestrator build their `PolicyContext` through this one shared
    factory, so locked-screen mutation blocking and permission grants are
    actually live in both, not just exercised by isolated policy tests.
    Granting a permission (`runtime.permissions.grant(capability_id)`)
    takes effect on the very next dispatch, with no separate "apply the
    grant" step, since the factory re-reads the store each call rather
    than snapshotting it once.
    """

    manifests = (
        *system_info_manifests(),
        app_open_manifest(),
        *browser_manifests(),
        *media_manifests(),
        *meta_manifests(),
    )
    registry = CapabilityRegistry(manifests)
    operations = operation_controller or OperationController()
    state = state_machine or StateMachine()
    confirmations = confirmation or ConfirmationService()
    lock = lock_state or WindowsLockStateAdapter()
    permissions = permission_store or JsonPermissionStore(
        get_settings().data_dir / "permissions.json"
    )
    audit = InMemoryAuditSink()
    policy = PolicyEngine(registry, FixedWindowRateLimiter())
    handlers = {
        **system_info_handlers(lambda: datetime.now().astimezone()),
        "app.open": make_app_open_handler(launcher),
        **browser_handlers(browser_opener),
        **media_handlers(key_presser),
        **meta_handlers(registry, operations, audit),
    }
    dispatcher = SerializedDispatcher(
        registry=registry,
        policy=policy,
        audit=audit,
        handlers=handlers,
    )
    planner = TextCommandPlanner(registry)

    def policy_context_factory() -> PolicyContext:
        return PolicyContext(
            locked_screen=lock.is_locked(),
            granted_capabilities=permissions.granted_capabilities(),
        )

    inputs = input_bus or EventBus(max_size=100)
    input_adapter = InputAdapter(inputs)
    outputs = output_bus or EventBus(max_size=100)
    orchestrator = EventOrchestrator(
        input_bus=inputs,
        output_bus=outputs,
        planner=planner,
        dispatcher=dispatcher,
        operations=operations,
        confirmation=confirmations,
        permission_store=permissions,
        state_machine=state,
        policy_context_factory=policy_context_factory,
    )
    return Runtime(
        registry=registry,
        audit=audit,
        dispatcher=dispatcher,
        operations=operations,
        planner=planner,
        confirmation=confirmations,
        permissions=permissions,
        policy_context_factory=policy_context_factory,
        input_bus=inputs,
        input_adapter=input_adapter,
        output_bus=outputs,
        orchestrator=orchestrator,
        state_machine=state,
    )
