"""Safe media-control capability.

Migrated from the old prototype's media keyboard shortcuts as reference
material only. The trusted runtime exposes a small action allowlist and
injects the key presser for tests, so verification never sends real media
keys.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from importlib import import_module

from visionai.capabilities.dispatcher import CapabilityHandler
from visionai.capabilities.manifest import (
    CapabilityManifest,
    IdempotencyMode,
    ParameterSpec,
    ParameterType,
)
from visionai.core.cancellation import CancellationToken
from visionai.core.events import ActionRequest, ActionResult, RiskLevel

ALLOWED_MEDIA_ACTIONS: Mapping[str, str] = {
    "mute": "volumemute",
    "next": "nexttrack",
    "play_pause": "playpause",
    "previous": "prevtrack",
    "volume_down": "volumedown",
    "volume_up": "volumeup",
}

KeyPresser = Callable[[str], None]


def default_key_presser(key: str) -> None:
    """Press one allowlisted media key."""

    try:
        pyautogui = import_module("pyautogui")
    except ImportError as exc:
        raise OSError("pyautogui is not installed") from exc
    pyautogui.press(key)


def media_control_manifest() -> CapabilityManifest:
    """Return the manifest for media keyboard control."""

    return CapabilityManifest(
        id="media.control",
        description="Send one allowlisted media key action.",
        parameters={
            "action": ParameterSpec(
                type=ParameterType.STRING,
                required=True,
                description=f"One of: {', '.join(sorted(ALLOWED_MEDIA_ACTIONS))}.",
            )
        },
        risk_level=RiskLevel.REVERSIBLE,
        rate_limit_per_minute=30,
        timeout_seconds=3,
        idempotency=IdempotencyMode.NON_IDEMPOTENT,
        audit_category="media.control",
        handler_id="media.control",
    )


def media_manifests() -> tuple[CapabilityManifest, ...]:
    """Return all built-in media capability manifests."""

    return (media_control_manifest(),)


def make_media_control_handler(
    key_presser: KeyPresser = default_key_presser,
) -> CapabilityHandler:
    """Create a handler that sends one allowlisted media key."""

    def handle(request: ActionRequest, cancellation: CancellationToken) -> ActionResult:
        requested = str(request.arguments.get("action", "")).strip().lower()
        key = ALLOWED_MEDIA_ACTIONS.get(requested)
        if key is None:
            return ActionResult(
                request_id=request.id,
                success=False,
                message=f"'{requested}' is not an allowlisted media action.",
            )
        try:
            key_presser(key)
        except OSError as exc:
            return ActionResult(
                request_id=request.id,
                success=False,
                message=f"Could not control media: {exc}",
            )
        return ActionResult(
            request_id=request.id,
            success=True,
            message=f"Media action sent: {requested}.",
        )

    return handle


def media_handlers(
    key_presser: KeyPresser = default_key_presser,
) -> dict[str, CapabilityHandler]:
    """Return all built-in media handlers."""

    return {"media.control": make_media_control_handler(key_presser)}
