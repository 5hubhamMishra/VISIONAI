"""Console entry point for the safe local runtime."""

from __future__ import annotations

import argparse

from visionai.core.events import ActionRequest
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
            "system.clear_history",
            "system.help",
            "system.stop",
            "app.open",
            "browser.open",
            "browser.search",
            "media.control",
        ),
        default="system.time",
    )
    parser.add_argument("--format", default=None)
    parser.add_argument("--app", default=None, help="Application to open (app.open only).")
    parser.add_argument("--site", default=None, help="Website to open (browser.open only).")
    parser.add_argument("--query", default=None, help="Search query (browser.search only).")
    parser.add_argument("--media-action", default=None, help="Media action (media.control only).")
    parser.add_argument("--text", default=None, help="Plan and run one safe typed command.")
    args = parser.parse_args()

    runtime = build_runtime()
    if args.text is not None:
        _intent, plan = runtime.planner.plan(args.text)
        if not plan.steps:
            print(plan.summary)
            return 1
        result = runtime.dispatcher.dispatch(plan.steps[0], runtime.policy_context_factory())
        print(result.message)
        if not result.success:
            return 1
        return 0

    arguments: dict[str, str] = {}
    if args.format is not None:
        arguments["format"] = args.format
    if args.app is not None:
        arguments["app"] = args.app
    if args.site is not None:
        arguments["site"] = args.site
    if args.query is not None:
        arguments["query"] = args.query
    if args.media_action is not None:
        arguments["action"] = args.media_action

    manifest = runtime.registry.get(args.capability)
    request = ActionRequest(
        capability_id=args.capability,
        arguments=arguments,
        risk_level=manifest.risk_level,
    )
    result = runtime.dispatcher.dispatch(request, runtime.policy_context_factory())
    print(result.message)
    if not result.success:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
