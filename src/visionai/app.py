"""Console entry point for the safe local runtime."""

from __future__ import annotations

import argparse

from visionai.core.events import ActionRequest
from visionai.policy import PolicyContext
from visionai.runtime import build_runtime


def main() -> int:
    """Run one registered capability through the full policy and dispatcher path."""

    parser = argparse.ArgumentParser(prog="visionai")
    parser.add_argument(
        "capability",
        nargs="?",
        choices=(
            "system.time",
            "system.date",
            "system.battery",
            "system.health",
            "system.capabilities",
            "system.help",
            "app.open",
        ),
        default="system.time",
    )
    parser.add_argument("--format", default=None)
    parser.add_argument("--app", default=None, help="Application to open (app.open only).")
    args = parser.parse_args()

    runtime = build_runtime()
    arguments: dict[str, str] = {}
    if args.format is not None:
        arguments["format"] = args.format
    if args.app is not None:
        arguments["app"] = args.app

    manifest = runtime.registry.get(args.capability)
    request = ActionRequest(
        capability_id=args.capability,
        arguments=arguments,
        risk_level=manifest.risk_level,
    )
    result = runtime.dispatcher.dispatch(request, PolicyContext())
    print(result.message)
    if not result.success:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
