from uuid import uuid4

from visionai.capabilities import (
    CapabilityManifest,
    CapabilityRegistry,
    IdempotencyMode,
    ParameterSpec,
    ParameterType,
)
from visionai.core.events import ActionRequest, RiskLevel
from visionai.policy import FixedWindowRateLimiter, PolicyContext, PolicyEngine


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


def _rate_limited_manifest() -> CapabilityManifest:
    return CapabilityManifest(
        id="browser.search",
        description="Open an encoded search.",
        parameters={
            "query": ParameterSpec(
                type=ParameterType.STRING,
                required=True,
                description="Search query.",
            )
        },
        risk_level=RiskLevel.REVERSIBLE,
        rate_limit_per_minute=1,
        timeout_seconds=5,
        idempotency=IdempotencyMode.NON_IDEMPOTENT,
        audit_category="browser",
        handler_id="browser.search",
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
    assert no_permission.requires_permission is True
    assert no_confirmation.allowed is False
    assert no_confirmation.requires_confirmation is True
    assert no_confirmation.requires_permission is False
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


def test_policy_rejects_unsupported_platform() -> None:
    registry = CapabilityRegistry([_open_site_manifest()])
    engine = PolicyEngine(registry)
    request = ActionRequest(
        capability_id="browser.open_site",
        arguments={"url": "https://example.com"},
        risk_level=RiskLevel.REVERSIBLE,
    )

    decision = engine.evaluate(request, PolicyContext(platform="linux"))

    assert decision.allowed is False
    assert decision.reason == "capability is not supported on this platform"


def test_policy_rejects_prohibited_capability_as_defense_in_depth(monkeypatch) -> None:
    # CapabilityRegistry.register() already refuses to register a PROHIBITED
    # manifest, so this branch cannot be reached through the real registry.
    # It exists as a second, independent gate in PolicyEngine.evaluate()
    # itself and is worth proving directly rather than trusting the registry
    # alone to keep a prohibited capability from ever being evaluated.
    registry = CapabilityRegistry([_open_site_manifest()])
    prohibited = _open_site_manifest().model_copy(update={"risk_level": RiskLevel.PROHIBITED})
    monkeypatch.setattr(registry, "get", lambda capability_id: prohibited)
    engine = PolicyEngine(registry)
    request = ActionRequest(
        capability_id="browser.open_site",
        arguments={"url": "https://example.com"},
        risk_level=RiskLevel.REVERSIBLE,
    )

    decision = engine.evaluate(request, PolicyContext())

    assert decision.allowed is False
    assert decision.reason == "prohibited capability"


def _numeric_manifest() -> CapabilityManifest:
    return CapabilityManifest(
        id="media.set_volume",
        description="Set the system volume.",
        parameters={
            "level": ParameterSpec(
                type=ParameterType.INTEGER,
                required=True,
                description="Target volume level.",
            ),
            "fade_seconds": ParameterSpec(
                type=ParameterType.NUMBER,
                required=True,
                description="Fade duration in seconds.",
            ),
            "mute": ParameterSpec(
                type=ParameterType.BOOLEAN,
                required=True,
                description="Whether to mute instead.",
            ),
        },
        risk_level=RiskLevel.REVERSIBLE,
        rate_limit_per_minute=10,
        timeout_seconds=5,
        idempotency=IdempotencyMode.NON_IDEMPOTENT,
        audit_category="media",
        handler_id="media.set_volume",
    )


def test_policy_rejects_wrong_integer_argument_type() -> None:
    registry = CapabilityRegistry([_numeric_manifest()])
    engine = PolicyEngine(registry)
    request = ActionRequest(
        capability_id="media.set_volume",
        arguments={"level": "loud", "fade_seconds": 1.0, "mute": False},
        risk_level=RiskLevel.REVERSIBLE,
    )

    decision = engine.evaluate(request, PolicyContext())

    assert decision.allowed is False
    assert decision.reason == "argument has wrong type: level"


def test_policy_rejects_bool_for_integer_argument() -> None:
    # bool is a subclass of int in Python; a stray True/False must not be
    # silently accepted as a valid integer argument.
    registry = CapabilityRegistry([_numeric_manifest()])
    engine = PolicyEngine(registry)
    request = ActionRequest(
        capability_id="media.set_volume",
        arguments={"level": True, "fade_seconds": 1.0, "mute": False},
        risk_level=RiskLevel.REVERSIBLE,
    )

    decision = engine.evaluate(request, PolicyContext())

    assert decision.allowed is False
    assert decision.reason == "argument has wrong type: level"


def test_policy_rejects_wrong_number_argument_type() -> None:
    registry = CapabilityRegistry([_numeric_manifest()])
    engine = PolicyEngine(registry)
    request = ActionRequest(
        capability_id="media.set_volume",
        arguments={"level": 5, "fade_seconds": "fast", "mute": False},
        risk_level=RiskLevel.REVERSIBLE,
    )

    decision = engine.evaluate(request, PolicyContext())

    assert decision.allowed is False
    assert decision.reason == "argument has wrong type: fade_seconds"


def test_policy_rejects_bool_for_number_argument() -> None:
    registry = CapabilityRegistry([_numeric_manifest()])
    engine = PolicyEngine(registry)
    request = ActionRequest(
        capability_id="media.set_volume",
        arguments={"level": 5, "fade_seconds": True, "mute": False},
        risk_level=RiskLevel.REVERSIBLE,
    )

    decision = engine.evaluate(request, PolicyContext())

    assert decision.allowed is False
    assert decision.reason == "argument has wrong type: fade_seconds"


def test_policy_rejects_wrong_boolean_argument_type() -> None:
    registry = CapabilityRegistry([_numeric_manifest()])
    engine = PolicyEngine(registry)
    request = ActionRequest(
        capability_id="media.set_volume",
        arguments={"level": 5, "fade_seconds": 1.0, "mute": "yes"},
        risk_level=RiskLevel.REVERSIBLE,
    )

    decision = engine.evaluate(request, PolicyContext())

    assert decision.allowed is False
    assert decision.reason == "argument has wrong type: mute"


def test_policy_accepts_valid_numeric_and_boolean_arguments() -> None:
    registry = CapabilityRegistry([_numeric_manifest()])
    engine = PolicyEngine(registry)
    request = ActionRequest(
        capability_id="media.set_volume",
        arguments={"level": 5, "fade_seconds": 1.5, "mute": False},
        risk_level=RiskLevel.REVERSIBLE,
    )

    decision = engine.evaluate(request, PolicyContext())

    assert decision.allowed is True


def test_policy_can_check_rate_limit_without_consuming_it() -> None:
    registry = CapabilityRegistry([_rate_limited_manifest()])
    limiter = FixedWindowRateLimiter(clock=lambda: 100.0)
    engine = PolicyEngine(registry, limiter)
    context = PolicyContext()
    request = ActionRequest(
        capability_id="browser.search",
        arguments={"query": "visionai"},
        risk_level=RiskLevel.REVERSIBLE,
    )

    preflight = engine.evaluate(request, context, consume_rate_limit=False)
    first = engine.evaluate(request, context)
    second = engine.evaluate(
        ActionRequest(
            capability_id="browser.search",
            arguments={"query": "visionai"},
            risk_level=RiskLevel.REVERSIBLE,
        ),
        context,
    )

    assert preflight.allowed is True
    assert first.allowed is True
    assert second.allowed is False
    assert second.reason == "rate limit exceeded"
