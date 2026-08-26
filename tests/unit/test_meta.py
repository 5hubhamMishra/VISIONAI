from dataclasses import replace

from visionai.capabilities import CapabilityRegistry
from visionai.capabilities.meta import (
    make_system_capabilities_handler,
    make_system_clear_history_handler,
    make_system_help_handler,
    make_system_stop_handler,
    meta_manifests,
    system_capabilities_manifest,
    system_help_manifest,
)
from visionai.capabilities.system_info import system_info_manifests
from visionai.core.cancellation import CancellationToken, OperationController
from visionai.core.events import ActionRequest, AuditEvent, RiskLevel
from visionai.observability import InMemoryAuditSink
from visionai.platform.lock_state import StaticLockStateAdapter
from visionai.policy import PolicyContext
from visionai.policy.permissions import JsonPermissionStore
from visionai.runtime import build_runtime

_TOKEN = CancellationToken()


def test_meta_manifests_register_as_read_only() -> None:
    registry = CapabilityRegistry(meta_manifests())

    assert registry.get("system.capabilities").risk_level == RiskLevel.READ_ONLY
    assert registry.get("system.help").risk_level == RiskLevel.READ_ONLY
    assert registry.get("system.stop").risk_level == RiskLevel.READ_ONLY


def test_clear_history_manifest_is_sensitive_and_gated() -> None:
    registry = CapabilityRegistry(meta_manifests())
    manifest = registry.get("system.clear_history")

    assert manifest.risk_level == RiskLevel.SENSITIVE
    assert manifest.permission_required is True
    assert manifest.confirmation_required is True


def test_capabilities_handler_lists_registered_manifests_sorted_by_id() -> None:
    registry = CapabilityRegistry(
        (system_capabilities_manifest(), system_help_manifest(), *system_info_manifests())
    )
    handler = make_system_capabilities_handler(registry)

    result = handler(
        ActionRequest(capability_id="system.capabilities", risk_level=RiskLevel.READ_ONLY), _TOKEN
    )

    assert result.success is True
    assert "system.battery:" in result.message
    assert "system.time:" in result.message
    lines = result.message.splitlines()[1:]
    assert lines == sorted(lines)


def test_capabilities_handler_reports_empty_registry() -> None:
    registry = CapabilityRegistry(())
    handler = make_system_capabilities_handler(registry)

    result = handler(
        ActionRequest(capability_id="system.capabilities", risk_level=RiskLevel.READ_ONLY), _TOKEN
    )

    assert result.message == "No capabilities are registered."


def test_help_handler_reports_the_current_capability_count() -> None:
    registry = CapabilityRegistry(system_info_manifests())
    handler = make_system_help_handler(registry)

    result = handler(
        ActionRequest(capability_id="system.help", risk_level=RiskLevel.READ_ONLY), _TOKEN
    )

    assert result.success is True
    assert str(len(system_info_manifests())) in result.message


def test_runtime_dispatches_system_capabilities_and_lists_itself() -> None:
    runtime = build_runtime()
    request = ActionRequest(capability_id="system.capabilities", risk_level=RiskLevel.READ_ONLY)

    result = runtime.dispatcher.dispatch(request, PolicyContext())

    assert result.success is True
    assert "system.capabilities:" in result.message
    assert "app.open:" in result.message


def test_runtime_dispatches_system_help() -> None:
    runtime = build_runtime()
    request = ActionRequest(capability_id="system.help", risk_level=RiskLevel.READ_ONLY)

    result = runtime.dispatcher.dispatch(request, PolicyContext())

    assert result.success is True
    assert "VisionAI" in result.message


def test_stop_handler_reports_when_no_operation_is_running() -> None:
    controller = OperationController()
    handler = make_system_stop_handler(controller)

    result = handler(
        ActionRequest(capability_id="system.stop", risk_level=RiskLevel.READ_ONLY), _TOKEN
    )

    assert result.success is True
    assert result.message == "No operation is currently running."


def test_stop_handler_cancels_active_operation() -> None:
    controller = OperationController()
    token = controller.begin_operation()
    handler = make_system_stop_handler(controller)

    result = handler(
        ActionRequest(capability_id="system.stop", risk_level=RiskLevel.READ_ONLY), _TOKEN
    )

    assert result.success is True
    assert result.message == "Stop requested."
    assert token.is_cancelled is True


def test_runtime_dispatches_system_stop() -> None:
    runtime = build_runtime()
    token = runtime.operations.begin_operation()
    request = ActionRequest(capability_id="system.stop", risk_level=RiskLevel.READ_ONLY)

    result = runtime.dispatcher.dispatch(request, PolicyContext(locked_screen=True))

    assert result.success is True
    assert token.is_cancelled is True
    assert runtime.audit.list()[-1].category == "system.control"


def test_clear_history_handler_clears_the_audit_sink() -> None:
    audit = InMemoryAuditSink()
    audit.record(AuditEvent(category="test", actor="system", summary="pre-existing entry"))
    handler = make_system_clear_history_handler(audit)

    result = handler(
        ActionRequest(capability_id="system.clear_history", risk_level=RiskLevel.SENSITIVE),
        _TOKEN,
    )

    assert result.success is True
    assert result.message == "Audit history cleared."
    assert audit.list() == ()


def test_runtime_denies_clear_history_without_permission() -> None:
    runtime = build_runtime(lock_state=StaticLockStateAdapter(locked=False))
    request = ActionRequest(capability_id="system.clear_history", risk_level=RiskLevel.SENSITIVE)

    result = runtime.dispatcher.dispatch(request, runtime.policy_context_factory())

    assert result.success is False
    assert result.message == "permission has not been granted"


def test_runtime_denies_clear_history_with_permission_but_no_confirmation(tmp_path) -> None:
    permissions = JsonPermissionStore(tmp_path / "permissions.json")
    permissions.grant("system.clear_history")
    runtime = build_runtime(
        lock_state=StaticLockStateAdapter(locked=False), permission_store=permissions
    )
    request = ActionRequest(capability_id="system.clear_history", risk_level=RiskLevel.SENSITIVE)

    result = runtime.dispatcher.dispatch(request, runtime.policy_context_factory())

    assert result.success is False
    assert result.message == "fresh confirmation is required"


def test_runtime_clears_history_once_permitted_and_confirmed(tmp_path) -> None:
    permissions = JsonPermissionStore(tmp_path / "permissions.json")
    permissions.grant("system.clear_history")
    runtime = build_runtime(
        lock_state=StaticLockStateAdapter(locked=False), permission_store=permissions
    )
    runtime.audit.record(AuditEvent(category="test", actor="system", summary="old entry"))
    request = ActionRequest(capability_id="system.clear_history", risk_level=RiskLevel.SENSITIVE)
    context = replace(
        runtime.policy_context_factory(), confirmed_request_ids=frozenset({request.id})
    )

    result = runtime.dispatcher.dispatch(request, context)

    assert result.success is True
    assert result.message == "Audit history cleared."
    # The dispatcher's own post-execution audit record for this call is the
    # only entry left -- clearing history does not erase evidence a clear
    # happened.
    assert len(runtime.audit.list()) == 1
    assert runtime.audit.list()[0].summary == "Audit history cleared."
