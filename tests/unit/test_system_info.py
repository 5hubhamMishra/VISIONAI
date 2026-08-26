from datetime import datetime

from visionai.capabilities import CapabilityRegistry
from visionai.capabilities.system_info import (
    BatteryStatus,
    HealthSnapshot,
    make_system_battery_handler,
    make_system_date_handler,
    make_system_health_handler,
    make_system_time_handler,
    system_info_manifests,
)
from visionai.core.events import ActionRequest, RiskLevel
from visionai.policy import PolicyContext
from visionai.runtime import build_runtime


def _fixed_clock() -> datetime:
    return datetime(2026, 8, 26, 9, 7, 5)


def test_system_info_manifests_register_as_read_only() -> None:
    registry = CapabilityRegistry(system_info_manifests())

    assert registry.get("system.time").risk_level == RiskLevel.READ_ONLY
    assert registry.get("system.date").risk_level == RiskLevel.READ_ONLY
    assert registry.get("system.battery").risk_level == RiskLevel.READ_ONLY
    assert registry.get("system.health").risk_level == RiskLevel.READ_ONLY


def test_system_time_handler_formats_supported_outputs() -> None:
    handler = make_system_time_handler(_fixed_clock)
    base = {"capability_id": "system.time", "risk_level": RiskLevel.READ_ONLY}

    result_24h = handler(ActionRequest(**base, arguments={"format": "24h"}))
    result_12h = handler(ActionRequest(**base, arguments={"format": "12h"}))
    result_iso = handler(ActionRequest(**base, arguments={"format": "iso"}))

    assert result_24h.message == "It is 09:07:05."
    assert result_12h.message == "It is 09:07:05 AM."
    assert result_iso.message == "It is 2026-08-26T09:07:05."


def test_system_date_handler_formats_supported_outputs() -> None:
    handler = make_system_date_handler(_fixed_clock)
    base = {"capability_id": "system.date", "risk_level": RiskLevel.READ_ONLY}

    result_long = handler(ActionRequest(**base, arguments={"format": "long"}))
    result_short = handler(ActionRequest(**base, arguments={"format": "short"}))
    result_iso = handler(ActionRequest(**base, arguments={"format": "iso"}))

    assert result_long.message == "Today is Wednesday, August 26, 2026."
    assert result_short.message == "Today is 2026-08-26."
    assert result_iso.message == "Today is 2026-08-26."


def test_system_info_handlers_reject_unsupported_formats_without_side_effect() -> None:
    time_result = make_system_time_handler(_fixed_clock)(
        ActionRequest(
            capability_id="system.time",
            risk_level=RiskLevel.READ_ONLY,
            arguments={"format": "epoch"},
        )
    )
    date_result = make_system_date_handler(_fixed_clock)(
        ActionRequest(
            capability_id="system.date",
            risk_level=RiskLevel.READ_ONLY,
            arguments={"format": "julian"},
        )
    )

    assert time_result.success is False
    assert time_result.message == "Unsupported time format."
    assert date_result.success is False
    assert date_result.message == "Unsupported date format."


def test_system_battery_handler_reports_no_battery() -> None:
    handler = make_system_battery_handler(lambda: BatteryStatus(percent=None, plugged_in=None))

    result = handler(ActionRequest(capability_id="system.battery", risk_level=RiskLevel.READ_ONLY))

    assert result.success is True
    assert result.message == "No battery detected."


def test_system_battery_handler_reports_charge_and_power_source() -> None:
    handler = make_system_battery_handler(
        lambda: BatteryStatus(percent=87.4, plugged_in=True)
    )

    result = handler(ActionRequest(capability_id="system.battery", risk_level=RiskLevel.READ_ONLY))

    assert result.success is True
    assert result.message == "Battery is at 87% and plugged in."


def test_system_battery_handler_reports_on_battery_power() -> None:
    handler = make_system_battery_handler(
        lambda: BatteryStatus(percent=42.0, plugged_in=False)
    )

    result = handler(ActionRequest(capability_id="system.battery", risk_level=RiskLevel.READ_ONLY))

    assert result.message == "Battery is at 42% and on battery power."


def test_system_health_handler_reports_cpu_and_memory() -> None:
    handler = make_system_health_handler(
        lambda: HealthSnapshot(cpu_percent=12.3, memory_percent=55.6)
    )

    result = handler(ActionRequest(capability_id="system.health", risk_level=RiskLevel.READ_ONLY))

    assert result.success is True
    assert result.message == "CPU is at 12% and memory is at 56%."


def test_runtime_dispatches_system_time_through_policy_and_audit() -> None:
    runtime = build_runtime()
    request = ActionRequest(capability_id="system.time", risk_level=RiskLevel.READ_ONLY)

    result = runtime.dispatcher.dispatch(request, PolicyContext())

    assert result.success is True
    assert result.message.startswith("It is ")
    assert runtime.audit.list()[0].category == "system.info"


def test_runtime_dispatches_system_health_with_real_probe() -> None:
    runtime = build_runtime()
    request = ActionRequest(capability_id="system.health", risk_level=RiskLevel.READ_ONLY)

    result = runtime.dispatcher.dispatch(request, PolicyContext())

    assert result.success is True
    assert result.message.startswith("CPU is at ")
    assert "memory is at" in result.message


def test_runtime_dispatches_system_battery_with_real_probe() -> None:
    runtime = build_runtime()
    request = ActionRequest(capability_id="system.battery", risk_level=RiskLevel.READ_ONLY)

    result = runtime.dispatcher.dispatch(request, PolicyContext())

    assert result.success is True
    assert result.message in {"No battery detected."} or result.message.startswith("Battery is at ")


def test_policy_rejects_unknown_system_info_arguments_before_handler() -> None:
    registry = CapabilityRegistry(system_info_manifests())
    runtime = build_runtime()
    request = ActionRequest(
        capability_id="system.time",
        risk_level=RiskLevel.READ_ONLY,
        arguments={"command": "calc"},
    )

    result = runtime.dispatcher.dispatch(request, PolicyContext())

    assert registry.contains("system.time") is True
    assert result.success is False
    assert result.message == "unknown argument: command"
    assert runtime.audit.list()[0].summary == "unknown argument: command"
