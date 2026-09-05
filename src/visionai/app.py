"""Console entry point for the safe local runtime."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import threading
from collections.abc import AsyncIterator, Callable, Sequence
from typing import TYPE_CHECKING, Protocol, cast

from pydantic import ValidationError

from visionai.config import (
    default_secret_store,
    default_user_settings_store,
    effective_log_level,
    get_settings,
    resolve_anthropic_api_key,
)
from visionai.config.user_settings import effective_wake_word
from visionai.core.cancellation import CancellationToken
from visionai.core.errors import ProviderError, StorageError
from visionai.core.events import ActionPlan, ActionRequest, ActionResult, EventBase, GestureEvent
from visionai.intelligence import (
    DeterministicFallbackProvider,
    LLMProvider,
    LLMQuery,
    suggest_command_result,
)
from visionai.observability import configure_logging
from visionai.orchestration import WakeWordGate, WakeWordListeningLoop, WakeWordVoiceRunner
from visionai.platform.camera import LandmarkAdapter
from visionai.recognition import GestureCaptureLoop, GestureListeningLoop, TemporalGestureRecognizer
from visionai.runtime import Runtime, build_runtime

if TYPE_CHECKING:
    import numpy as np

    from visionai.orchestration.microphone_capture import MicrophonePushToTalk
    from visionai.platform.microphone import MicrophoneCapture
    from visionai.platform.webcam import WebcamLandmarkAdapter

_WAKE_WORD_LISTEN_CHUNK_SECONDS = 4.0


class _MicrophoneDevice(Protocol):
    index: int
    name: str
    max_input_channels: int


def _list_input_devices() -> Sequence[_MicrophoneDevice]:
    from visionai.platform.microphone import list_input_devices

    return cast(Sequence[_MicrophoneDevice], list_input_devices())


def _build_landmark_adapter() -> WebcamLandmarkAdapter:
    from visionai.platform.webcam import WebcamLandmarkAdapter

    return WebcamLandmarkAdapter()


def _build_cancellation_token() -> CancellationToken:
    return CancellationToken()


def _build_microphone_capture() -> MicrophoneCapture:
    from visionai.platform.microphone import default_microphone_capture

    return default_microphone_capture()


def _build_transcriber() -> Callable[[np.ndarray], str]:
    from visionai.platform.stt import default_transcriber

    return default_transcriber()


def _build_llm_provider() -> LLMProvider:
    """Build the configured LLM provider, defaulting to the no-network fallback.

    Mirrors the other `_build_*` factories: injectable for tests, and the
    heavy `anthropic` import only happens inside `AnthropicProvider`'s own
    constructor, so this function -- and importing `app` at all -- never
    requires the `intelligence` extra unless a provider is actually configured.
    """

    settings = get_settings()
    if settings.llm_provider == "none":
        return DeterministicFallbackProvider()
    if settings.llm_provider == "local":
        from visionai.intelligence.local_provider import LocalLlamaProvider

        model_path = settings.local_model_path
        if model_path is None:
            raise ValueError(
                "No local model path configured. Set VISIONAI_LOCAL_MODEL_PATH to "
                "a GGUF model file already present on disk."
            )
        if not model_path.is_file():
            raise ValueError(f"Local model file not found: {model_path}")
        return LocalLlamaProvider(model_path=str(model_path))

    from visionai.intelligence.anthropic_provider import AnthropicProvider

    api_key = resolve_anthropic_api_key(settings)
    if api_key is None:
        raise ValueError(
            "No Anthropic API key found. Set VISIONAI_ANTHROPIC_API_KEY or store one "
            "with `visionai --set-api-key`."
        )
    return AnthropicProvider(api_key=api_key, model=settings.llm_model)


async def _continuous_transcripts(
    capture: MicrophoneCapture,
    transcribe: Callable[[np.ndarray], str],
    cancellation: CancellationToken,
) -> AsyncIterator[str]:
    """Record fixed-length chunks and yield each one's non-empty transcript.

    The smallest real continuous-listening source: no VAD or streaming
    STT, just repeated record/transcribe cycles until cancelled. Mirrors
    `GestureCaptureLoop`'s "one blocking read per iteration" shape.
    """

    while not cancellation.is_cancelled:
        capture.start()
        await asyncio.sleep(_WAKE_WORD_LISTEN_CHUNK_SECONDS)
        audio = capture.stop()
        text = transcribe(audio)
        if text:
            yield text


def _run_wake_word_listen(
    runtime: Runtime,
    capture: MicrophoneCapture,
    transcribe: Callable[[np.ndarray], str],
    wake_word: str,
    cancellation: CancellationToken,
) -> int:
    """Drive `WakeWordListeningLoop` on a worker thread until Ctrl+C.

    Mirrors `_run_gesture_listen`: real microphone capture/transcription
    happen off the main thread so a `KeyboardInterrupt` can cancel cleanly,
    and any dispatched action's result is printed once the session ends.
    """

    runner = WakeWordVoiceRunner(runtime.input_adapter, gate=WakeWordGate(wake_word))
    result: dict[str, int] = {}
    failure: list[Exception] = []

    def _worker() -> None:
        async def run_session() -> int:
            consumer = asyncio.create_task(runtime.orchestrator.run_until_closed())
            listening_loop = WakeWordListeningLoop(
                runner=runner,
                source=_continuous_transcripts(capture, transcribe, cancellation),
                cancellation=cancellation,
            )
            try:
                return await listening_loop.run()
            finally:
                runtime.input_bus.close()
                await consumer
                while runtime.output_bus.size:
                    output = await runtime.output_bus.next_event()
                    if isinstance(output, ActionResult):
                        print(output.message)

        try:
            result["accepted"] = asyncio.run(run_session())
        except Exception as exc:
            failure.append(exc)

    worker = threading.Thread(target=_worker, daemon=True)
    worker.start()
    try:
        while worker.is_alive():
            worker.join(timeout=0.2)
    except KeyboardInterrupt:
        cancellation.cancel()
        worker.join()
    if failure:
        raise RuntimeError(f"wake-word listener failed: {failure[0]}") from failure[0]
    return result.get("accepted", 0)


def _run_gesture_listen(
    runtime: Runtime,
    landmark_adapter: LandmarkAdapter,
    recognizer: TemporalGestureRecognizer,
    cancellation: CancellationToken,
) -> int:
    """Drive `GestureListeningLoop` on a worker thread until Ctrl+C.

    Mirrors the desktop Stop button: the loop runs off the calling thread so
    a `KeyboardInterrupt` on the main thread can call `cancellation.cancel()`
    and wait for a clean stop, instead of aborting mid-frame and losing the
    landmark adapter's `close()` or the confirmed-gesture count.
    """

    capture = GestureCaptureLoop(
        landmark_adapter=landmark_adapter,
        recognizer=recognizer,
        input_adapter=runtime.input_adapter,
    )
    listening_loop = GestureListeningLoop(
        capture=capture, cancellation=cancellation, stop_gesture_id="open_palm"
    )
    result: dict[str, int] = {}
    failure: list[Exception] = []

    def _worker() -> None:
        try:
            async def run_session() -> int:
                consumer = asyncio.create_task(runtime.orchestrator.run_until_closed())
                voice_runner: MicrophonePushToTalk | None = None

                async def on_gesture(event: GestureEvent) -> None:
                    nonlocal voice_runner
                    if event.gesture_id == "closed_fist" and voice_runner is None:
                        try:
                            from visionai.orchestration.microphone_capture import (
                                MicrophonePushToTalk,
                            )

                            voice_runner = MicrophonePushToTalk(
                                input_adapter=runtime.input_adapter,
                                capture=_build_microphone_capture(),
                                transcribe=_build_transcriber(),
                            )
                            voice_runner.press()
                            print("Voice command listening started. Show an open palm to send it.")
                        except (ImportError, OSError, RuntimeError, ValueError) as exc:
                            voice_runner = None
                            print(f"Voice input unavailable: {exc}")
                    elif event.gesture_id == "open_palm" and voice_runner is not None:
                        transcript = await voice_runner.release()
                        voice_runner = None
                        if transcript is None or not transcript.text.strip():
                            print("No speech recognized.")
                        else:
                            print(f"Recognized command: {transcript.text.strip()}")
                            print("Voice command sent.")

                listening_loop.on_confirmed = on_gesture
                try:
                    return await listening_loop.run()
                finally:
                    try:
                        if voice_runner is not None:
                            voice_runner.cancel()
                    finally:
                        runtime.input_bus.close()
                        await consumer
                    while runtime.output_bus.size:
                        output = await runtime.output_bus.next_event()
                        if isinstance(output, ActionResult):
                            print(output.message)

            try:
                result["confirmed"] = asyncio.run(run_session())
            except Exception as exc:
                failure.append(exc)
        finally:
            close = getattr(landmark_adapter, "close", None)
            if close is not None:
                close()

    worker = threading.Thread(target=_worker, daemon=True)
    worker.start()
    try:
        while worker.is_alive():
            worker.join(timeout=0.2)
    except KeyboardInterrupt:
        cancellation.cancel()
        worker.join()
    if failure:
        raise RuntimeError(f"gesture listener failed: {failure[0]}") from failure[0]
    return result.get("confirmed", 0)


async def _run_gesture_capture(
    runtime: Runtime,
    landmark_adapter: LandmarkAdapter,
    recognizer: TemporalGestureRecognizer,
    max_frames: int,
) -> str:
    loop = GestureCaptureLoop(
        landmark_adapter=landmark_adapter,
        recognizer=recognizer,
        input_adapter=runtime.input_adapter,
    )
    try:
        for _ in range(max_frames):
            event = await loop.capture_once()
            if event is not None:
                return (
                    f"Gesture detected: {event.gesture_id} ({event.hand} hand, "
                    f"held {event.hold_ms}ms, confidence {event.confidence:.2f})."
                )
    finally:
        close = getattr(landmark_adapter, "close", None)
        if close is not None:
            close()
    return "No gesture detected."


async def _run_wake_word_text(
    runtime: Runtime, utterance: str, wake_word: str
) -> tuple[bool, str]:
    runner = WakeWordVoiceRunner(runtime.input_adapter, gate=WakeWordGate(wake_word))
    event = await runner.observe(utterance)
    if event is None:
        return False, "No wake-word command detected."
    await runtime.orchestrator.process_event(event)
    outputs: list[EventBase] = []
    while runtime.output_bus.size:
        outputs.append(await runtime.output_bus.next_event())
    result = next((output for output in outputs if isinstance(output, ActionResult)), None)
    if result is not None:
        return result.success, result.message
    plan = next((output for output in outputs if isinstance(output, ActionPlan)), None)
    return False, plan.summary if plan is not None else "No response."


def main() -> int:
    """Run one registered capability through the full policy and dispatcher path."""

    settings_store = default_user_settings_store()
    configure_logging(effective_log_level(settings_store))

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
    parser.add_argument(
        "--wake-word-text", default=None, help="Run one already-transcribed wake-word command."
    )
    parser.add_argument("--list-microphones", action="store_true", help="List audio input devices.")
    parser.add_argument(
        "--gesture-frames",
        type=int,
        default=None,
        help="Capture up to N real webcam frames and report the first confirmed gesture.",
    )
    parser.add_argument(
        "--gesture-listen",
        action="store_true",
        help="Continuously watch for gestures until Ctrl+C, then report the confirmed count.",
    )
    parser.add_argument(
        "--wake-word-listen",
        action="store_true",
        help="Continuously listen for the wake word via the real microphone until Ctrl+C.",
    )
    parser.add_argument(
        "--ask",
        default=None,
        help="Ask the configured LLM one question. Conversation only -- dispatches nothing.",
    )
    parser.add_argument(
        "--suggest",
        default=None,
        help="Ask the LLM to propose a command, then ask before dispatching it.",
    )
    parser.add_argument(
        "--set-api-key",
        action="store_true",
        help="Store an Anthropic API key in the OS keychain (prompts, hidden input).",
    )
    parser.add_argument(
        "--delete-api-key",
        action="store_true",
        help="Remove any Anthropic API key stored in the OS keychain.",
    )
    args = parser.parse_args()

    if args.set_api_key:
        try:
            key = getpass.getpass("Anthropic API key: ")
        except (EOFError, KeyboardInterrupt):
            print("Cancelled.")
            return 0
        if not key.strip():
            print("No key entered. Nothing stored.")
            return 1
        try:
            default_secret_store().set("anthropic_api_key", key.strip())
        except (ImportError, StorageError) as exc:
            print(f"Could not store the key: {exc}")
            return 1
        print("API key stored in the OS keychain.")
        return 0

    if args.delete_api_key:
        try:
            default_secret_store().delete("anthropic_api_key")
        except (ImportError, StorageError) as exc:
            print(f"Could not remove the key: {exc}")
            return 1
        print("API key removed from the OS keychain, if it was there.")
        return 0

    if args.ask is not None:
        try:
            provider = _build_llm_provider()
            reply = provider.respond(LLMQuery(text=args.ask))
        except (ImportError, ValueError, ProviderError, ValidationError) as exc:
            print(f"Could not get an answer: {exc}")
            return 1
        print(reply.text)
        return 0

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
    if args.wake_word_listen:
        wake_word = effective_wake_word(settings_store)
        print(f"Listening for the wake word ('{wake_word}'). Press Ctrl+C to stop.")
        try:
            accepted = _run_wake_word_listen(
                runtime,
                _build_microphone_capture(),
                _build_transcriber(),
                wake_word,
                _build_cancellation_token(),
            )
        except Exception as exc:
            print(f"Listening failed: {exc}")
            return 1
        print(f"Stopped. Accepted {accepted} command(s).")
        return 0
    if args.gesture_listen:
        print("Listening for gestures. Press Ctrl+C to stop.")
        try:
            confirmed = _run_gesture_listen(
                runtime,
                _build_landmark_adapter(),
                TemporalGestureRecognizer(),
                _build_cancellation_token(),
            )
        except Exception as exc:
            print(f"Listening failed: {exc}")
            return 1
        print(f"Stopped. Confirmed {confirmed} gesture(s).")
        return 0
    if args.gesture_frames is not None:
        message = asyncio.run(
            _run_gesture_capture(
                runtime,
                _build_landmark_adapter(),
                TemporalGestureRecognizer(),
                args.gesture_frames,
            )
        )
        print(message)
        return 0
    if args.wake_word_text is not None:
        success, message = asyncio.run(
            _run_wake_word_text(runtime, args.wake_word_text, effective_wake_word(settings_store))
        )
        print(message)
        return 0 if success else 1
    if args.suggest is not None:
        try:
            provider = _build_llm_provider()
        except (ImportError, ValueError) as exc:
            print(f"Could not get a suggestion: {exc}")
            return 1
        if isinstance(provider, DeterministicFallbackProvider):
            print(provider.respond(LLMQuery(text=args.suggest)).text)
            return 0
        utterance = args.suggest
        try:
            suggestion = suggest_command_result(provider, utterance)
            if suggestion.clarification is not None:
                print(suggestion.clarification)
                try:
                    answer = input("> ").strip()
                except (EOFError, KeyboardInterrupt):
                    answer = ""
                if answer:
                    utterance = f"{utterance} {answer}"
                    suggestion = suggest_command_result(provider, utterance)
            phrase = suggestion.phrase
        except (ProviderError, ValidationError) as exc:
            print(f"Could not get a suggestion: {exc}")
            return 1
        if phrase is None:
            print("No matching command found.")
            return 0
        _intent, plan = runtime.planner.plan(phrase)
        if not plan.steps:
            print("No matching command found.")
            return 0
        print(f"Proposed: {plan.summary}")
        try:
            answer = input("Execute this command? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer not in {"y", "yes"}:
            print("Cancelled.")
            return 0
        result = runtime.dispatcher.dispatch(plan.steps[0], runtime.policy_context_factory())
        print(result.message)
        return 0 if result.success else 1
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
