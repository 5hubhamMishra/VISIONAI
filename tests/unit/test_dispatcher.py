import pytest

from visionai.capabilities import (
    CapabilityManifest,
    CapabilityRegistry,
    IdempotencyMode,
    ParameterSpec,
    ParameterType,
    SerializedDispatcher,
)
from visionai.core.cancellation import CancellationToken
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
            "system.time": lambda request, cancellation: ActionResult(
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

    def handler(request: ActionRequest, cancellation) -> ActionResult:
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


def test_dispatcher_evaluate_checks_policy_without_executing_or_consuming_rate_limit() -> None:
    registry = CapabilityRegistry([_manifest()])
    audit = InMemoryAuditSink()
    calls = 0

    def handler(request: ActionRequest, cancellation) -> ActionResult:
        nonlocal calls
        calls += 1
        return ActionResult(request_id=request.id, success=True, message="ok")

    dispatcher = SerializedDispatcher(
        registry=registry,
        policy=PolicyEngine(registry, FixedWindowRateLimiter(clock=lambda: 100.0)),
        audit=audit,
        handlers={"system.time": handler},
    )
    request = ActionRequest(capability_id="system.time", risk_level=RiskLevel.READ_ONLY)

    decision = dispatcher.evaluate(request, PolicyContext())
    result = dispatcher.dispatch(request, PolicyContext())
    denied = dispatcher.dispatch(
        ActionRequest(capability_id="system.time", risk_level=RiskLevel.READ_ONLY),
        PolicyContext(),
    )

    assert decision.allowed is True
    assert result.success is True
    assert denied.success is False
    assert calls == 1
    assert len(audit.list()) == 2


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
        handlers={"clipboard.read": lambda request, cancellation: ActionResult(
            request_id=request.id, success=True, message="ok"
        )},
    )
    # risk_level here is spoofed as READ_ONLY even though the registered
    # capability is SENSITIVE; the audit must trust the manifest, not this.
    request = ActionRequest(capability_id="clipboard.read", risk_level=RiskLevel.READ_ONLY)

    result = dispatcher.dispatch(request, PolicyContext())

    assert result.success is False
    assert audit.list()[-1].risk_level == RiskLevel.SENSITIVE


def test_dispatcher_skips_the_handler_when_the_token_is_already_cancelled() -> None:
    """A request cancelled before its handler ever runs must have no effect --
    e.g. Stop raced ahead of a request still queued behind the serialized
    dispatcher's lock."""

    registry = CapabilityRegistry([_manifest()])
    audit = InMemoryAuditSink()
    calls = 0

    def handler(request: ActionRequest, cancellation: CancellationToken) -> ActionResult:
        nonlocal calls
        calls += 1
        return ActionResult(request_id=request.id, success=True, message="ok")

    dispatcher = SerializedDispatcher(
        registry=registry,
        policy=PolicyEngine(registry),
        audit=audit,
        handlers={"system.time": handler},
    )
    request = ActionRequest(capability_id="system.time", risk_level=RiskLevel.READ_ONLY)
    token = CancellationToken()
    token.cancel()

    result = dispatcher.dispatch(request, PolicyContext(), cancellation=token)

    assert calls == 0
    assert result.success is False
    assert result.message == "Operation was cancelled before it started."
    assert audit.list()[-1].summary == "Operation was cancelled before it started."


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


def test_register_handler_adds_a_new_handler_that_dispatch_can_then_use() -> None:
    """No built-in wiring calls register_handler today (runtime.py builds the
    full handlers dict up front and passes it to the constructor), but it is
    still public API a future caller could use to add a handler afterward --
    prove it actually wires a dispatchable handler, not just mutates state
    nothing reads."""
    registry = CapabilityRegistry([_manifest()])
    dispatcher = SerializedDispatcher(
        registry=registry,
        policy=PolicyEngine(registry),
        audit=InMemoryAuditSink(),
    )
    request = ActionRequest(capability_id="system.time", risk_level=RiskLevel.READ_ONLY)

    dispatcher.register_handler(
        "system.time",
        lambda request, cancellation: ActionResult(
            request_id=request.id, success=True, message="It is 10:00."
        ),
    )
    result = dispatcher.dispatch(request, PolicyContext())

    assert result.success is True
    assert result.message == "It is 10:00."


def test_register_handler_rejects_a_duplicate_handler_id() -> None:
    registry = CapabilityRegistry([_manifest()])
    dispatcher = SerializedDispatcher(
        registry=registry,
        policy=PolicyEngine(registry),
        audit=InMemoryAuditSink(),
        handlers={
            "system.time": lambda request, cancellation: ActionResult(
                request_id=request.id, success=True, message="ok"
            )
        },
    )

    with pytest.raises(DispatchError, match="handler already registered: system.time"):
        dispatcher.register_handler(
            "system.time",
            lambda request, cancellation: ActionResult(
                request_id=request.id, success=True, message="replaced"
            ),
        )
