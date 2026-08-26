import pytest

from visionai.capabilities import CapabilityRegistry, SerializedDispatcher
from visionai.capabilities.applications import (
    ALLOWED_APPLICATIONS,
    app_open_manifest,
    make_app_open_handler,
)
from visionai.core.cancellation import CancellationToken
from visionai.core.errors import DispatchError
from visionai.core.events import ActionRequest, RiskLevel
from visionai.observability import InMemoryAuditSink
from visionai.policy import FixedWindowRateLimiter, PolicyContext, PolicyEngine
from visionai.runtime import build_runtime

_TOKEN = CancellationToken()


def _app_open_request(app: str | None = None, **extra: str) -> ActionRequest:
    arguments = dict(extra)
    if app is not None:
        arguments["app"] = app
    return ActionRequest(
        capability_id="app.open", risk_level=RiskLevel.REVERSIBLE, arguments=arguments
    )


def test_app_open_manifest_is_reversible_and_requires_no_permission_or_confirmation() -> None:
    manifest = app_open_manifest()

    assert manifest.risk_level == RiskLevel.REVERSIBLE
    assert manifest.permission_required is False
    assert manifest.confirmation_required is False


def test_handler_launches_the_allowlisted_executable_for_a_known_app() -> None:
    launched: list[str] = []
    handler = make_app_open_handler(launcher=launched.append)

    result = handler(_app_open_request("notepad"), _TOKEN)

    assert result.success is True
    assert launched == [ALLOWED_APPLICATIONS["notepad"]]


def test_handler_is_case_and_whitespace_insensitive_for_known_apps() -> None:
    launched: list[str] = []
    handler = make_app_open_handler(launcher=launched.append)

    handler(_app_open_request("  Calculator  "), _TOKEN)

    assert launched == [ALLOWED_APPLICATIONS["calculator"]]


def test_handler_rejects_an_unallowlisted_app_without_launching_anything() -> None:
    launched: list[str] = []
    handler = make_app_open_handler(launcher=launched.append)

    result = handler(_app_open_request("cmd"), _TOKEN)

    assert result.success is False
    assert "not an allowlisted application" in result.message
    assert launched == []


def test_handler_reports_failure_without_raising_when_launch_fails() -> None:
    def failing_launcher(executable: str) -> None:
        raise OSError("executable not found")

    handler = make_app_open_handler(launcher=failing_launcher)

    result = handler(_app_open_request("notepad"), _TOKEN)

    assert result.success is False
    assert "Could not open notepad" in result.message


def test_policy_rejects_unknown_app_open_arguments_before_handler() -> None:
    registry = CapabilityRegistry([app_open_manifest()])
    launched: list[str] = []
    policy = PolicyEngine(registry)
    request = _app_open_request("notepad", extra="unexpected")

    decision = policy.evaluate(request, PolicyContext())

    assert decision.allowed is False
    assert decision.reason == "unknown argument: extra"
    assert launched == []


def test_policy_rejects_missing_required_app_argument() -> None:
    registry = CapabilityRegistry([app_open_manifest()])
    policy = PolicyEngine(registry)
    request = _app_open_request()

    decision = policy.evaluate(request, PolicyContext())

    assert decision.allowed is False
    assert decision.reason == "missing required argument: app"


def test_rate_limit_blocks_app_open_after_the_configured_limit() -> None:
    registry = CapabilityRegistry([app_open_manifest()])
    manifest = registry.get("app.open")
    policy = PolicyEngine(registry, FixedWindowRateLimiter(clock=lambda: 100.0))
    request = _app_open_request("notepad")
    attempts = manifest.rate_limit_per_minute + 1

    decisions = [policy.evaluate(request, PolicyContext()) for _ in range(attempts)]

    assert all(decision.allowed for decision in decisions[:-1])
    assert decisions[-1].allowed is False
    assert decisions[-1].reason == "rate limit exceeded"


def test_runtime_dispatches_app_open_with_injected_launcher_and_audits_it() -> None:
    launched: list[str] = []
    runtime = build_runtime(launcher=launched.append)
    request = _app_open_request("paint")

    result = runtime.dispatcher.dispatch(request, PolicyContext())

    assert result.success is True
    assert launched == [ALLOWED_APPLICATIONS["paint"]]
    audited = runtime.audit.list()[-1]
    assert audited.category == "app.launch"
    assert audited.risk_level == RiskLevel.REVERSIBLE


def test_runtime_denies_unallowlisted_app_with_the_real_default_launcher() -> None:
    """Safe to exercise the real default_launcher here: the app is rejected
    before the launcher is ever called, so nothing actually spawns."""
    runtime = build_runtime()
    request = _app_open_request("powershell")

    result = runtime.dispatcher.dispatch(request, PolicyContext())

    assert result.success is False
    assert "not an allowlisted application" in result.message


def test_dispatcher_rejects_missing_handler_for_app_open_if_not_registered() -> None:
    registry = CapabilityRegistry([app_open_manifest()])
    dispatcher = SerializedDispatcher(
        registry=registry, policy=PolicyEngine(registry), audit=InMemoryAuditSink()
    )
    request = _app_open_request("notepad")

    with pytest.raises(DispatchError):
        dispatcher.dispatch(request, PolicyContext())
