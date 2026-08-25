import pytest

from visionai.capabilities import (
    CapabilityManifest,
    CapabilityRegistry,
    IdempotencyMode,
    ParameterSpec,
    ParameterType,
)
from visionai.core.errors import CapabilityError, UnregisteredCapabilityError
from visionai.core.events import RiskLevel


def _manifest(capability_id: str = "system.time") -> CapabilityManifest:
    return CapabilityManifest(
        id=capability_id,
        description="Return the current local time.",
        parameters={
            "format": ParameterSpec(
                type=ParameterType.STRING,
                required=False,
                description="Display format.",
            )
        },
        risk_level=RiskLevel.READ_ONLY,
        rate_limit_per_minute=30,
        timeout_seconds=2,
        idempotency=IdempotencyMode.IDEMPOTENT,
        audit_category="system.info",
        handler_id="system.time",
    )


def test_registry_returns_registered_manifest() -> None:
    registry = CapabilityRegistry([_manifest()])

    assert registry.get("system.time").id == "system.time"


def test_registry_rejects_duplicate_ids() -> None:
    registry = CapabilityRegistry([_manifest()])

    with pytest.raises(CapabilityError):
        registry.register(_manifest())


def test_registry_rejects_unknown_capability() -> None:
    registry = CapabilityRegistry()

    with pytest.raises(UnregisteredCapabilityError):
        registry.get("missing.capability")


def test_registry_rejects_prohibited_capability() -> None:
    manifest = _manifest("unsafe.shell")
    manifest = manifest.model_copy(update={"risk_level": RiskLevel.PROHIBITED})

    with pytest.raises(CapabilityError):
        CapabilityRegistry([manifest])
