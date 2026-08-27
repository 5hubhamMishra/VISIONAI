"""Console entry point for the safe local runtime."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import Protocol, cast

from visionai.config import default_user_settings_store, effective_log_level
from visionai.core.events import ActionRequest
from visionai.observability import configure_logging
from visionai.runtime import build_runtime


class _MicrophoneDevice(Protocol):
    index: int
    name: str
    max_input_channels: int


def _list_input_devices() -> Sequence[_MicrophoneDevice]:
    from visionai.platform.microphone import list_input_devices

    return cast(Sequence[_MicrophoneDevice], list_input_devices())


def main() -> int:
    """Run one registered capability through the full policy and dispatcher path."""

    configure_logging(effective_log_level(default_user_settings_store()))

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
    parser.add_argument("--list-microphones", action="store_true", help="List audio input devices.")
    args = parser.parse_args()

    if args.list_microphones:
        try:
            devices = _list_input_devices()
        except Exception as exc:
            print(f"Could not list microphones: {exc}")
            return 1
        if not devices:
            print("No microphone input devices found.")
            return 0
        for device in devices:
            print(f"{device.index}: {device.name} ({device.max_input_channels} input channels)")
        return 0

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
