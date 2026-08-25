"""Console entry point for the safe local runtime."""

from __future__ import annotations

import argparse

from visionai.core.events import ActionRequest, RiskLevel
from visionai.policy import PolicyContext
from visionai.runtime import build_runtime


def main() -> int:
    """Run a read-only built-in capability through policy and dispatcher."""

    parser = argparse.ArgumentParser(prog="visionai")
    parser.add_argument(
        "capability",
        nargs="?",
        choices=("system.time", "system.date"),
        default="system.time",
    )
    parser.add_argument("--format", default=None)
    args = parser.parse_args()

    runtime = build_runtime()
    arguments = {}
    if args.format is not None:
        arguments["format"] = args.format
    request = ActionRequest(
        capability_id=args.capability,
        arguments=arguments,
        risk_level=RiskLevel.READ_ONLY,
    )
    result = runtime.dispatcher.dispatch(request, PolicyContext())
    print(result.message)
    if not result.success:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
