from visionai.capabilities import CapabilityRegistry
from visionai.capabilities.media import (
    ALLOWED_MEDIA_ACTIONS,
    make_media_control_handler,
    media_control_manifest,
    media_manifests,
)
from visionai.core.cancellation import CancellationToken
from visionai.core.events import ActionRequest, RiskLevel
from visionai.policy import PolicyContext
from visionai.runtime import build_runtime

_TOKEN = CancellationToken()


def _media_request(action: str | None = None, **extra: str) -> ActionRequest:
    arguments = dict(extra)
    if action is not None:
        arguments["action"] = action
    return ActionRequest(
        capability_id="media.control",
        risk_level=RiskLevel.REVERSIBLE,
        arguments=arguments,
    )


def test_media_manifest_is_reversible_and_allowlisted() -> None:
    manifest = media_control_manifest()

    assert manifest.risk_level == RiskLevel.REVERSIBLE
    assert manifest.permission_required is False
    assert manifest.confirmation_required is False
    assert set(manifest.parameters) == {"action"}


def test_media_manifests_register() -> None:
    registry = CapabilityRegistry(media_manifests())

    assert registry.get("media.control").risk_level == RiskLevel.REVERSIBLE


def test_handler_presses_the_allowlisted_key_for_a_known_action() -> None:
    pressed: list[str] = []
    handler = make_media_control_handler(key_presser=pressed.append)

    result = handler(_media_request("  Volume_Up  "), _TOKEN)

    assert result.success is True
    assert pressed == [ALLOWED_MEDIA_ACTIONS["volume_up"]]


def test_handler_rejects_unknown_action_without_pressing_anything() -> None:
    pressed: list[str] = []
    handler = make_media_control_handler(key_presser=pressed.append)

    result = handler(_media_request("launch_shell"), _TOKEN)

    assert result.success is False
    assert "not an allowlisted media action" in result.message
    assert pressed == []


def test_handler_reports_key_presser_failure_without_raising() -> None:
    def failing_key_presser(key: str) -> None:
        raise OSError(f"{key} unavailable")

    handler = make_media_control_handler(key_presser=failing_key_presser)

    result = handler(_media_request("mute"), _TOKEN)

    assert result.success is False
    assert "Could not control media" in result.message


def test_runtime_dispatches_media_control_and_audits_it() -> None:
    pressed: list[str] = []
    runtime = build_runtime(key_presser=pressed.append)

    result = runtime.dispatcher.dispatch(_media_request("next"), PolicyContext())

    assert result.success is True
    assert pressed == [ALLOWED_MEDIA_ACTIONS["next"]]
    audited = runtime.audit.list()[-1]
    assert audited.category == "media.control"
    assert audited.risk_level == RiskLevel.REVERSIBLE


def test_policy_rejects_missing_and_unknown_media_arguments() -> None:
    pressed: list[str] = []
    runtime = build_runtime(key_presser=pressed.append)

    missing = runtime.dispatcher.dispatch(_media_request(), PolicyContext())
    unknown = runtime.dispatcher.dispatch(_media_request("mute", extra="x"), PolicyContext())

    assert missing.success is False
    assert missing.message == "missing required argument: action"
    assert unknown.success is False
    assert unknown.message == "unknown argument: extra"
    assert pressed == []
