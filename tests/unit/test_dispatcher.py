import pytest

from visionai.capabilities import (
    CapabilityManifest,
    CapabilityRegistry,
    IdempotencyMode,
    ParameterSpec,
    ParameterType,
    SerializedDispatcher,
)
from visionai.core.errors import DispatchError
from visionai.core.events import ActionRequest, ActionResult, RiskLevel
from visionai.observability import InMemoryAuditSink
from visionai.policy import FixedWindowRateLimiter, PolicyContext, PolicyEngine


def _manifest() -> CapabilityManifest:
    return CapabilityManifest(
        id="system.time",
        description="Return the current local time.",
        parameters={
            "format": ParameterSpec(
                type=ParameterType.STRING,
                required=False,
                description="Display format.",
            )
        },
        risk_level=RiskLevel.READ_ONLY,
        rate_limit_per_minute=1,
        timeout_seconds=2,
        idempotency=IdempotencyMode.IDEMPOTENT,
        audit_category="system.info",
        handler_id="system.time",
    )


def test_dispatcher_executes_registered_handler_and_audits_result() -> None:
    registry = CapabilityRegistry([_manifest()])
    audit = InMemoryAuditSink()
    dispatcher = SerializedDispatcher(
        registry=registry,
        policy=PolicyEngine(registry),
        audit=audit,
        handlers={
            "system.time": lambda request: ActionResult(
                request_id=request.id,
                success=True,
                message="It is 10:00.",
            )
        },
    )
    request = ActionRequest(
        capability_id="system.time",
        arguments={"format": "24h"},
        risk_level=RiskLevel.READ_ONLY,
    )

    result = dispatcher.dispatch(request, PolicyContext())

    assert result.success is True
    assert audit.list()[0].summary == "It is 10:00."


def test_dispatcher_returns_policy_denial_without_second_handler_call() -> None:
    registry = CapabilityRegistry([_manifest()])
    audit = InMemoryAuditSink()
    calls = 0

    def handler(request: ActionRequest) -> ActionResult:
        nonlocal calls
        calls += 1
        return ActionResult(request_id=request.id, success=True, message="ok")

    dispatcher = SerializedDispatcher(
        registry=registry,
        policy=PolicyEngine(registry, FixedWindowRateLimiter(clock=lambda: 100.0)),
        audit=audit,
        handlers={"system.time": handler},
    )
    first = ActionRequest(capability_id="system.time", risk_level=RiskLevel.READ_ONLY)
    second = ActionRequest(capability_id="system.time", risk_level=RiskLevel.READ_ONLY)

    assert dispatcher.dispatch(first, PolicyContext()).success is True
    denied = dispatcher.dispatch(second, PolicyContext())

    assert denied.success is False
    assert denied.message == "rate limit exceeded"
    assert calls == 1
    assert audit.list()[-1].summary == "rate limit exceeded"


def test_dispatcher_audits_denials_with_the_manifests_risk_level_not_the_requests() -> None:
    """A caller-supplied risk_level must not be able to understate severity in the audit log."""
    sensitive_manifest = CapabilityManifest(
        id="clipboard.read",
        description="Read the clipboard.",
        risk_level=RiskLevel.SENSITIVE,
        permission_required=True,
        confirmation_required=True,
        rate_limit_per_minute=10,
        timeout_seconds=2,
        idempotency=IdempotencyMode.IDEMPOTENT,
        audit_category="clipboard",
        handler_id="clipboard.read",
    )
    registry = CapabilityRegistry([sensitive_manifest])
    audit = InMemoryAuditSink()
    dispatcher = SerializedDispatcher(
        registry=registry,
        policy=PolicyEngine(registry),
        audit=audit,
        handlers={"clipboard.read": lambda request: ActionResult(
            request_id=request.id, success=True, message="ok"
        )},
    )
    # risk_level here is spoofed as READ_ONLY even though the registered
    # capability is SENSITIVE; the audit must trust the manifest, not this.
    request = ActionRequest(capability_id="clipboard.read", risk_level=RiskLevel.READ_ONLY)

    result = dispatcher.dispatch(request, PolicyContext())

    assert result.success is False
    assert audit.list()[-1].risk_level == RiskLevel.SENSITIVE


def test_dispatcher_rejects_missing_handler_after_policy_allows() -> None:
    registry = CapabilityRegistry([_manifest()])
    dispatcher = SerializedDispatcher(
        registry=registry,
        policy=PolicyEngine(registry),
        audit=InMemoryAuditSink(),
    )
    request = ActionRequest(capability_id="system.time", risk_level=RiskLevel.READ_ONLY)

    with pytest.raises(DispatchError):
        dispatcher.dispatch(request, PolicyContext())
