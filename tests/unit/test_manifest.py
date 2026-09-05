import pytest
from pydantic import ValidationError

from visionai.capabilities import CapabilityManifest, IdempotencyMode
from visionai.core.events import RiskLevel


def _manifest_kwargs(**overrides: object) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "id": "system.time",
        "description": "Return the current local time.",
        "risk_level": RiskLevel.READ_ONLY,
        "rate_limit_per_minute": 30,
        "timeout_seconds": 2,
        "idempotency": IdempotencyMode.IDEMPOTENT,
        "audit_category": "system.info",
        "handler_id": "system.time",
    }
    kwargs.update(overrides)
    return kwargs


def test_sensitive_manifest_without_permission_required_is_rejected() -> None:
    with pytest.raises(ValidationError, match="require permission"):
        CapabilityManifest(
            **_manifest_kwargs(risk_level=RiskLevel.SENSITIVE, permission_required=False)
        )


def test_destructive_manifest_without_confirmation_required_is_rejected() -> None:
    with pytest.raises(ValidationError, match="destructive capabilities require confirmation"):
        CapabilityManifest(
            **_manifest_kwargs(
                risk_level=RiskLevel.DESTRUCTIVE,
                permission_required=True,
                confirmation_required=False,
            )
        )


def test_sensitive_manifest_with_permission_required_is_accepted() -> None:
    manifest = CapabilityManifest(
        **_manifest_kwargs(risk_level=RiskLevel.SENSITIVE, permission_required=True)
    )

    assert manifest.risk_level is RiskLevel.SENSITIVE


def test_destructive_manifest_with_both_controls_is_accepted() -> None:
    manifest = CapabilityManifest(
        **_manifest_kwargs(
            risk_level=RiskLevel.DESTRUCTIVE,
            permission_required=True,
            confirmation_required=True,
        )
    )

    assert manifest.risk_level is RiskLevel.DESTRUCTIVE
