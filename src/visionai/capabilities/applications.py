"""Open-allowlisted-application capability.

Migrated from ../jarvis/actions/executor.py as reference material only,
per docs/MIGRATION_QUARANTINE.md. The old code used
subprocess.Popen(cmd, shell=True) against a much larger app list that
included a shell, a terminal, and Task Manager -- each of those is
itself a general-purpose command surface, which would reintroduce the
arbitrary-execution risk this capability exists to avoid, so they are
deliberately excluded here. Every application is launched by its exact
executable name with shell=False -- no shell interpretation, no
argument string to inject into.
"""

from __future__ import annotations

# Used only via default_launcher below, with shell=False and an exact
# executable string taken from ALLOWED_APPLICATIONS, never user text.
import subprocess  # nosec B404
from collections.abc import Callable, Mapping

from visionai.capabilities.dispatcher import CapabilityHandler
from visionai.capabilities.manifest import (
    CapabilityManifest,
    IdempotencyMode,
    ParameterSpec,
    ParameterType,
)
from visionai.core.events import ActionRequest, ActionResult, RiskLevel

ALLOWED_APPLICATIONS: Mapping[str, str] = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
}

Launcher = Callable[[str], None]


def default_launcher(executable: str) -> None:
    """Launch `executable` with no shell interpretation and no arguments."""
    # executable always comes from ALLOWED_APPLICATIONS above, never user text.
    subprocess.Popen([executable], shell=False)  # nosec B603


def app_open_manifest() -> CapabilityManifest:
    """Return the manifest for the open-allowlisted-application capability."""

    return CapabilityManifest(
        id="app.open",
        description="Open one allowlisted desktop application.",
        parameters={
            "app": ParameterSpec(
                type=ParameterType.STRING,
                required=True,
                description=f"One of: {', '.join(sorted(ALLOWED_APPLICATIONS))}.",
            )
        },
        risk_level=RiskLevel.REVERSIBLE,
        rate_limit_per_minute=10,
        timeout_seconds=5,
        idempotency=IdempotencyMode.NON_IDEMPOTENT,
        audit_category="app.launch",
        handler_id="app.open",
    )


def make_app_open_handler(launcher: Launcher = default_launcher) -> CapabilityHandler:
    """Create a handler that launches one allowlisted application."""

    def handle(request: ActionRequest) -> ActionResult:
        requested = str(request.arguments.get("app", ""))
        executable = ALLOWED_APPLICATIONS.get(requested.strip().lower())
        if executable is None:
            return ActionResult(
                request_id=request.id,
                success=False,
                message=f"'{requested}' is not an allowlisted application.",
            )
        try:
            launcher(executable)
        except OSError as exc:
            return ActionResult(
                request_id=request.id,
                success=False,
                message=f"Could not open {requested}: {exc}",
            )
        return ActionResult(request_id=request.id, success=True, message=f"Opening {requested}.")

    return handle
