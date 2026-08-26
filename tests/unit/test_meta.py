from visionai.capabilities import CapabilityRegistry
from visionai.capabilities.meta import (
    make_system_capabilities_handler,
    make_system_help_handler,
    meta_manifests,
    system_capabilities_manifest,
    system_help_manifest,
)
from visionai.capabilities.system_info import system_info_manifests
from visionai.core.events import ActionRequest, RiskLevel
from visionai.policy import PolicyContext
from visionai.runtime import build_runtime


def test_meta_manifests_register_as_read_only() -> None:
    registry = CapabilityRegistry(meta_manifests())

    assert registry.get("system.capabilities").risk_level == RiskLevel.READ_ONLY
    assert registry.get("system.help").risk_level == RiskLevel.READ_ONLY


def test_capabilities_handler_lists_registered_manifests_sorted_by_id() -> None:
    registry = CapabilityRegistry(
        (system_capabilities_manifest(), system_help_manifest(), *system_info_manifests())
    )
    handler = make_system_capabilities_handler(registry)

    result = handler(
        ActionRequest(capability_id="system.capabilities", risk_level=RiskLevel.READ_ONLY)
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
        ActionRequest(capability_id="system.capabilities", risk_level=RiskLevel.READ_ONLY)
    )

    assert result.message == "No capabilities are registered."


def test_help_handler_reports_the_current_capability_count() -> None:
    registry = CapabilityRegistry(system_info_manifests())
    handler = make_system_help_handler(registry)

    result = handler(ActionRequest(capability_id="system.help", risk_level=RiskLevel.READ_ONLY))

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
