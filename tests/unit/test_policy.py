from uuid import uuid4

from visionai.capabilities import (
    CapabilityManifest,
    CapabilityRegistry,
    IdempotencyMode,
    ParameterSpec,
    ParameterType,
)
from visionai.core.events import ActionRequest, RiskLevel
from visionai.policy import PolicyContext, PolicyEngine


def _open_site_manifest() -> CapabilityManifest:
    return CapabilityManifest(
        id="browser.open_site",
        description="Open an allowlisted website.",
        parameters={
            "url": ParameterSpec(
                type=ParameterType.STRING,
                required=True,
                description="Allowlisted HTTPS URL.",
            )
        },
        risk_level=RiskLevel.REVERSIBLE,
        rate_limit_per_minute=10,
        timeout_seconds=5,
        idempotency=IdempotencyMode.NON_IDEMPOTENT,
        audit_category="browser",
        handler_id="browser.open_site",
    )


def _clipboard_manifest() -> CapabilityManifest:
    return CapabilityManifest(
        id="clipboard.read",
        description="Read clipboard text.",
        risk_level=RiskLevel.SENSITIVE,
        permission_required=True,
        confirmation_required=True,
        rate_limit_per_minute=10,
        timeout_seconds=3,
        idempotency=IdempotencyMode.IDEMPOTENT,
        audit_category="clipboard",
        handler_id="clipboard.read",
    )


def test_policy_allows_registered_low_risk_request() -> None:
    registry = CapabilityRegistry([_open_site_manifest()])
    engine = PolicyEngine(registry)
    request = ActionRequest(
        capability_id="browser.open_site",
        arguments={"url": "https://example.com"},
        risk_level=RiskLevel.REVERSIBLE,
    )

    decision = engine.evaluate(request, PolicyContext())

    assert decision.allowed is True


def test_policy_rejects_unknown_arguments() -> None:
    registry = CapabilityRegistry([_open_site_manifest()])
    engine = PolicyEngine(registry)
    request = ActionRequest(
        capability_id="browser.open_site",
        arguments={"url": "https://example.com", "raw_command": "calc"},
        risk_level=RiskLevel.REVERSIBLE,
    )

    decision = engine.evaluate(request, PolicyContext())

    assert decision.allowed is False
    assert decision.reason == "unknown argument: raw_command"


def test_policy_requires_permission_and_confirmation_for_sensitive_requests() -> None:
    registry = CapabilityRegistry([_clipboard_manifest()])
    engine = PolicyEngine(registry)
    request = ActionRequest(capability_id="clipboard.read", risk_level=RiskLevel.SENSITIVE)

    no_permission = engine.evaluate(request, PolicyContext())
    no_confirmation = engine.evaluate(
        request,
        PolicyContext(granted_capabilities=frozenset({"clipboard.read"})),
    )
    allowed = engine.evaluate(
        request,
        PolicyContext(
            granted_capabilities=frozenset({"clipboard.read"}),
            confirmed_request_ids=frozenset({request.id}),
        ),
    )

    assert no_permission.allowed is False
    assert no_permission.reason == "permission has not been granted"
    assert no_confirmation.allowed is False
    assert no_confirmation.requires_confirmation is True
    assert allowed.allowed is True


def test_policy_blocks_mutations_when_screen_is_locked() -> None:
    registry = CapabilityRegistry([_open_site_manifest()])
    engine = PolicyEngine(registry)
    request = ActionRequest(
        capability_id="browser.open_site",
        arguments={"url": "https://example.com"},
        risk_level=RiskLevel.REVERSIBLE,
    )

    decision = engine.evaluate(request, PolicyContext(locked_screen=True))

    assert decision.allowed is False
    assert "locked" in decision.reason


def test_policy_rejects_wrong_argument_type() -> None:
    registry = CapabilityRegistry([_open_site_manifest()])
    engine = PolicyEngine(registry)
    request = ActionRequest(
        capability_id="browser.open_site",
        arguments={"url": 42},
        risk_level=RiskLevel.REVERSIBLE,
    )

    decision = engine.evaluate(request, PolicyContext())

    assert decision.allowed is False
    assert decision.reason == "argument has wrong type: url"


def test_unrelated_confirmation_does_not_authorize_request() -> None:
    registry = CapabilityRegistry([_clipboard_manifest()])
    engine = PolicyEngine(registry)
    request = ActionRequest(capability_id="clipboard.read", risk_level=RiskLevel.SENSITIVE)

    decision = engine.evaluate(
        request,
        PolicyContext(
            granted_capabilities=frozenset({"clipboard.read"}),
            confirmed_request_ids=frozenset({uuid4()}),
        ),
    )

    assert decision.allowed is False
    assert decision.requires_confirmation is True
