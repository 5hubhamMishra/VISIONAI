from dataclasses import dataclass, field

import pytest

from visionai import app
from visionai.config.routines import RoutineStore
from visionai.config.secrets import InMemorySecretStore
from visionai.config.user_settings import UserSettingsStore
from visionai.core.cancellation import CancellationToken
from visionai.platform.camera import GestureCandidate, LandmarkAdapter, StaticLandmarkAdapter
from visionai.platform.lock_state import StaticLockStateAdapter
from visionai.platform.microphone import MicrophoneDevice
from visionai.recognition import TemporalGestureRecognizer
from visionai.runtime import build_runtime


@dataclass
class _CancelWhenExhausted:
    """Cancels a token once `total` reads happen, mirroring the recognition-level test double."""

    inner: LandmarkAdapter
    token: CancellationToken
    total: int
    _count: int = field(default=0, init=False)

    def read_candidate(self) -> GestureCandidate:
        self._count += 1
        candidate = self.inner.read_candidate()
        if self._count >= self.total:
            self.token.cancel()
        return candidate


def test_app_runs_default_time_capability(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["visionai"])

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert output.startswith("It is ")


def test_app_returns_failure_for_unsupported_format(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["visionai", "system.date", "--format", "julian"])

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "Unsupported date format." in output


def test_app_runs_system_capabilities(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["visionai", "system.capabilities"])

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "app.open:" in output


def test_app_runs_system_stop(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["visionai", "system.stop"])

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "No operation is currently running." in output


def test_app_runs_safe_text_command(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["visionai", "--text", "what time is it"])

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "It is " in output


def test_app_runs_a_wake_word_text_command(monkeypatch, capsys, tmp_path) -> None:
    launched: list[str] = []
    store = UserSettingsStore(tmp_path / "settings.json")
    store.set_wake_word("hey visionai")
    monkeypatch.setattr("visionai.app.default_user_settings_store", lambda: store)
    monkeypatch.setattr(
        "sys.argv", ["visionai", "--wake-word-text", "hey visionai open notepad"]
    )
    monkeypatch.setattr(
        "visionai.app.build_runtime", lambda: build_runtime(launcher=launched.append)
    )

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Opening notepad." in output
    assert launched == ["notepad.exe"]


def test_app_rejects_wake_word_text_without_matching_wake_word(
    monkeypatch, capsys, tmp_path
) -> None:
    launched: list[str] = []
    store = UserSettingsStore(tmp_path / "settings.json")
    monkeypatch.setattr("visionai.app.default_user_settings_store", lambda: store)
    monkeypatch.setattr("sys.argv", ["visionai", "--wake-word-text", "open notepad"])
    monkeypatch.setattr(
        "visionai.app.build_runtime", lambda: build_runtime(launcher=launched.append)
    )

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "No wake-word command detected." in output
    assert launched == []


class _FakeMicrophoneCapture:
    """No real hardware: `stop()` returns nothing meaningful, since `transcribe` is faked too."""

    def start(self) -> None:
        pass

    def stop(self) -> None:
        return None


class _FailingMicrophoneCapture(_FakeMicrophoneCapture):
    def stop(self) -> None:
        raise OSError("microphone read failed")


def test_app_reports_wake_word_worker_failure(monkeypatch, capsys, tmp_path) -> None:
    store = UserSettingsStore(tmp_path / "settings.json")
    monkeypatch.setattr("visionai.app.default_user_settings_store", lambda: store)
    monkeypatch.setattr("sys.argv", ["visionai", "--wake-word-listen"])
    monkeypatch.setattr("visionai.app._build_microphone_capture", _FailingMicrophoneCapture)
    monkeypatch.setattr("visionai.app._build_transcriber", lambda: (lambda audio: ""))
    monkeypatch.setattr("visionai.app._WAKE_WORD_LISTEN_CHUNK_SECONDS", 0.0)
    monkeypatch.setattr(
        "visionai.app.build_runtime", lambda: build_runtime(launcher=lambda _: None)
    )

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "Listening failed: wake-word listener failed: microphone read failed" in output


def test_app_wake_word_listen_accepts_matching_commands_until_cancelled(
    monkeypatch, capsys, tmp_path
) -> None:
    launched: list[str] = []
    store = UserSettingsStore(tmp_path / "settings.json")
    token = CancellationToken()
    transcripts = iter(["visionai open notepad", "background noise"])

    def _fake_transcribe(audio: object) -> str:
        try:
            return next(transcripts)
        except StopIteration:
            token.cancel()
            return ""

    monkeypatch.setattr("visionai.app.default_user_settings_store", lambda: store)
    monkeypatch.setattr("visionai.app._WAKE_WORD_LISTEN_CHUNK_SECONDS", 0.0)
    monkeypatch.setattr("sys.argv", ["visionai", "--wake-word-listen"])
    monkeypatch.setattr("visionai.app._build_microphone_capture", lambda: _FakeMicrophoneCapture())
    monkeypatch.setattr("visionai.app._build_transcriber", lambda: _fake_transcribe)
    monkeypatch.setattr("visionai.app._build_cancellation_token", lambda: token)
    monkeypatch.setattr(
        "visionai.app.build_runtime", lambda: build_runtime(launcher=launched.append)
    )

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Listening for the wake word ('visionai')." in output
    assert "Stopped. Accepted 1 command(s)." in output
    assert "Opening notepad." in output
    assert launched == ["notepad.exe"]


def test_app_wake_word_listen_reads_nothing_when_already_cancelled(
    monkeypatch, capsys, tmp_path
) -> None:
    launched: list[str] = []
    store = UserSettingsStore(tmp_path / "settings.json")
    token = CancellationToken()
    token.cancel()

    monkeypatch.setattr("visionai.app.default_user_settings_store", lambda: store)
    monkeypatch.setattr("visionai.app._WAKE_WORD_LISTEN_CHUNK_SECONDS", 0.0)
    monkeypatch.setattr("sys.argv", ["visionai", "--wake-word-listen"])
    monkeypatch.setattr("visionai.app._build_microphone_capture", lambda: _FakeMicrophoneCapture())
    monkeypatch.setattr(
        "visionai.app._build_transcriber", lambda: (lambda audio: "visionai open notepad")
    )
    monkeypatch.setattr("visionai.app._build_cancellation_token", lambda: token)
    monkeypatch.setattr(
        "visionai.app.build_runtime", lambda: build_runtime(launcher=launched.append)
    )

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Stopped. Accepted 0 command(s)." in output
    assert launched == []


def test_app_reports_first_confirmed_gesture(monkeypatch, capsys) -> None:
    candidates = [GestureCandidate(gesture_id="open_palm", hand="right", confidence=0.9)] * 3
    adapter = StaticLandmarkAdapter(candidates=candidates)
    times = iter([0.0, 0.1, 0.5])
    monkeypatch.setattr("sys.argv", ["visionai", "--gesture-frames", "5"])
    monkeypatch.setattr("visionai.app._build_landmark_adapter", lambda: adapter)
    monkeypatch.setattr(
        "visionai.app.TemporalGestureRecognizer",
        lambda: TemporalGestureRecognizer(clock=lambda: next(times)),
    )

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Gesture detected: open_palm (right hand, held 500ms, confidence 0.90)." in output


def test_app_reports_no_gesture_detected_within_frame_budget(monkeypatch, capsys) -> None:
    adapter = StaticLandmarkAdapter(candidates=[])
    monkeypatch.setattr("sys.argv", ["visionai", "--gesture-frames", "3"])
    monkeypatch.setattr("visionai.app._build_landmark_adapter", lambda: adapter)

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "No gesture detected." in output


def test_app_gesture_listen_counts_confirmed_votes_until_cancelled(monkeypatch, capsys) -> None:
    token = CancellationToken()
    candidates = [GestureCandidate(gesture_id="open_palm", hand="right", confidence=0.9)] * 3
    wrapped = _CancelWhenExhausted(StaticLandmarkAdapter(candidates=candidates), token, total=3)
    times = iter([0.0, 0.1, 0.5])
    monkeypatch.setattr("sys.argv", ["visionai", "--gesture-listen"])
    monkeypatch.setattr("visionai.app._build_landmark_adapter", lambda: wrapped)
    monkeypatch.setattr("visionai.app._build_cancellation_token", lambda: token)
    monkeypatch.setattr(
        "visionai.app.TemporalGestureRecognizer",
        lambda: TemporalGestureRecognizer(min_hold_ms=400, clock=lambda: next(times)),
    )

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Listening for gestures. Press Ctrl+C to stop." in output
    assert "Stopped. Confirmed 1 gesture(s)." in output


def test_app_gesture_listen_reads_nothing_when_already_cancelled(monkeypatch, capsys) -> None:
    token = CancellationToken()
    token.cancel()
    adapter = StaticLandmarkAdapter(
        candidates=[GestureCandidate(gesture_id="open_palm", hand="right", confidence=0.9)]
    )
    monkeypatch.setattr("sys.argv", ["visionai", "--gesture-listen"])
    monkeypatch.setattr("visionai.app._build_landmark_adapter", lambda: adapter)
    monkeypatch.setattr("visionai.app._build_cancellation_token", lambda: token)

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Stopped. Confirmed 0 gesture(s)." in output


@pytest.mark.parametrize("desktop", [False, True])
def test_cancelled_gesture_session_discards_pending_voice(monkeypatch, desktop: bool) -> None:
    token = CancellationToken()
    fist = GestureCandidate(gesture_id="closed_fist", hand="right", confidence=0.9)
    adapter = _CancelWhenExhausted(StaticLandmarkAdapter(candidates=[fist, fist]), token, 3)
    times = iter([0.0, 0.5, 0.6])
    recognizer = TemporalGestureRecognizer(clock=lambda: next(times))
    launched: list[str] = []
    transcribed: list[bool] = []
    stopped: list[bool] = []
    runtime = build_runtime(
        launcher=launched.append, lock_state=StaticLockStateAdapter(locked=False)
    )

    class Capture(_FakeMicrophoneCapture):
        def stop(self) -> None:
            stopped.append(True)

    def transcribe(audio: object) -> str:
        transcribed.append(True)
        return "open notepad"

    module = "visionai.ui.main_window" if desktop else "visionai.app"
    monkeypatch.setattr(f"{module}._build_microphone_capture", Capture)
    monkeypatch.setattr(f"{module}._build_transcriber", lambda: transcribe)
    if desktop:
        from visionai.ui.main_window import _GestureListenWorker

        worker = _GestureListenWorker(
            runtime=runtime, landmark_adapter=adapter, recognizer=recognizer, cancellation=token
        )
        errors: list[str] = []
        worker.failed.connect(errors.append)
        worker.run()
        assert errors == []
    else:
        assert app._run_gesture_listen(runtime, adapter, recognizer, token) == 1
    assert stopped == [True]
    assert transcribed == []
    assert launched == []


def test_app_gesture_listen_closed_fist_starts_and_open_palm_sends_voice_command(
    monkeypatch, capsys
) -> None:
    launched: list[str] = []
    candidates = [
        GestureCandidate(gesture_id="closed_fist", hand="right", confidence=0.9),
        GestureCandidate(gesture_id="closed_fist", hand="right", confidence=0.9),
        GestureCandidate(gesture_id="open_palm", hand="right", confidence=0.9),
        GestureCandidate(gesture_id="open_palm", hand="right", confidence=0.9),
    ]
    adapter = StaticLandmarkAdapter(candidates=candidates)
    times = iter([0.0, 0.5, 0.6, 1.1])
    monkeypatch.setattr("sys.argv", ["visionai", "--gesture-listen"])
    monkeypatch.setattr("visionai.app._build_landmark_adapter", lambda: adapter)
    monkeypatch.setattr(
        "visionai.app.TemporalGestureRecognizer",
        lambda: TemporalGestureRecognizer(min_hold_ms=400, clock=lambda: next(times)),
    )
    monkeypatch.setattr("visionai.app._build_microphone_capture", lambda: _FakeMicrophoneCapture())
    monkeypatch.setattr(
        "visionai.app._build_transcriber", lambda: (lambda audio: "open notepad")
    )
    monkeypatch.setattr(
        "visionai.app.build_runtime", lambda: build_runtime(launcher=launched.append)
    )

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Voice command listening started. Show an open palm to send it." in output
    assert "Voice command sent." in output
    assert "Opening notepad." in output
    assert launched == ["notepad.exe"]
    assert "Stopped. Confirmed 2 gesture(s)." in output


def test_app_gesture_listen_reports_when_voice_capture_is_unavailable(
    monkeypatch, capsys
) -> None:
    candidates = [
        GestureCandidate(gesture_id="closed_fist", hand="right", confidence=0.9),
        GestureCandidate(gesture_id="closed_fist", hand="right", confidence=0.9),
        GestureCandidate(gesture_id="open_palm", hand="right", confidence=0.9),
        GestureCandidate(gesture_id="open_palm", hand="right", confidence=0.9),
    ]
    adapter = StaticLandmarkAdapter(candidates=candidates)
    times = iter([0.0, 0.5, 0.6, 1.1])

    def _broken_capture() -> object:
        raise OSError("no microphone device available")

    monkeypatch.setattr("sys.argv", ["visionai", "--gesture-listen"])
    monkeypatch.setattr("visionai.app._build_landmark_adapter", lambda: adapter)
    monkeypatch.setattr(
        "visionai.app.TemporalGestureRecognizer",
        lambda: TemporalGestureRecognizer(min_hold_ms=400, clock=lambda: next(times)),
    )
    monkeypatch.setattr("visionai.app._build_microphone_capture", _broken_capture)

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Voice input unavailable: no microphone device available" in output
    assert "Voice command sent." not in output
    assert "Stopped. Confirmed 2 gesture(s)." in output


def test_app_lists_microphones_without_building_runtime(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["visionai", "--list-microphones"])
    monkeypatch.setattr(
        "visionai.app._list_input_devices",
        lambda: [MicrophoneDevice(index=3, name="Desk Mic", max_input_channels=2)],
    )
    monkeypatch.setattr(
        "visionai.app.build_runtime",
        lambda: pytest.fail("listing microphones must not build the runtime"),
    )

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "3: Desk Mic (2 input channels)" in output


def test_app_reports_microphone_listing_failure(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["visionai", "--list-microphones"])

    def fail() -> list[MicrophoneDevice]:
        raise RuntimeError("audio backend unavailable")

    monkeypatch.setattr("visionai.app._list_input_devices", fail)

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "Could not list microphones: audio backend unavailable" in output


def test_app_set_api_key_stores_it_in_the_keychain(monkeypatch, capsys) -> None:
    store = InMemorySecretStore()
    monkeypatch.setattr("sys.argv", ["visionai", "--set-api-key"])
    monkeypatch.setattr("getpass.getpass", lambda prompt: "sk-ant-fake-key")
    monkeypatch.setattr("visionai.app.default_secret_store", lambda: store)

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "API key stored in the OS keychain." in output
    assert store.get("anthropic_api_key") == "sk-ant-fake-key"


def test_app_set_api_key_stores_nothing_for_empty_input(monkeypatch, capsys) -> None:
    store = InMemorySecretStore()
    monkeypatch.setattr("sys.argv", ["visionai", "--set-api-key"])
    monkeypatch.setattr("getpass.getpass", lambda prompt: "   ")
    monkeypatch.setattr("visionai.app.default_secret_store", lambda: store)

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "No key entered. Nothing stored." in output
    assert store.get("anthropic_api_key") is None


def test_app_set_api_key_cancelled_stores_nothing(monkeypatch, capsys) -> None:
    store = InMemorySecretStore()

    def _interrupted(prompt: str) -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr("sys.argv", ["visionai", "--set-api-key"])
    monkeypatch.setattr("getpass.getpass", _interrupted)
    monkeypatch.setattr("visionai.app.default_secret_store", lambda: store)

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Cancelled." in output
    assert store.get("anthropic_api_key") is None


def test_app_delete_api_key_removes_it(monkeypatch, capsys) -> None:
    store = InMemorySecretStore()
    store.set("anthropic_api_key", "sk-ant-fake-key")
    monkeypatch.setattr("sys.argv", ["visionai", "--delete-api-key"])
    monkeypatch.setattr("visionai.app.default_secret_store", lambda: store)

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "API key removed from the OS keychain, if it was there." in output
    assert store.get("anthropic_api_key") is None


def test_app_ask_uses_the_fallback_by_default_and_builds_no_runtime(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["visionai", "--ask", "what is 2+2?"])
    monkeypatch.setattr(
        "visionai.app.build_runtime",
        lambda: pytest.fail("--ask must not build the runtime"),
    )

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "No LLM provider is configured" in output


def test_app_ask_prints_the_injected_providers_reply(monkeypatch, capsys) -> None:
    class _FakeProvider:
        def respond(self, query: object) -> object:
            from visionai.intelligence import LLMReply

            return LLMReply(text="four")

    monkeypatch.setattr("sys.argv", ["visionai", "--ask", "what is 2+2?"])
    monkeypatch.setattr("visionai.app._build_llm_provider", lambda: _FakeProvider())

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert output.strip() == "four"


def test_app_ask_reports_a_provider_construction_failure(monkeypatch, capsys) -> None:
    def _broken_provider() -> object:
        raise ValueError("VISIONAI_ANTHROPIC_API_KEY is not set")

    monkeypatch.setattr("sys.argv", ["visionai", "--ask", "what is 2+2?"])
    monkeypatch.setattr("visionai.app._build_llm_provider", _broken_provider)

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "Could not get an answer: VISIONAI_ANTHROPIC_API_KEY is not set" in output


def test_build_llm_provider_none_returns_the_deterministic_fallback(monkeypatch) -> None:
    from visionai.config.settings import Settings
    from visionai.intelligence import DeterministicFallbackProvider

    monkeypatch.setattr("visionai.app.get_settings", lambda: Settings(llm_provider="none"))

    provider = app._build_llm_provider()

    assert isinstance(provider, DeterministicFallbackProvider)


def test_build_llm_provider_local_without_a_configured_path_raises(monkeypatch) -> None:
    from visionai.config.settings import Settings

    monkeypatch.setattr(
        "visionai.app.get_settings", lambda: Settings(llm_provider="local")
    )

    with pytest.raises(ValueError, match="No local model path configured"):
        app._build_llm_provider()


def test_build_llm_provider_local_with_a_missing_file_raises(monkeypatch, tmp_path) -> None:
    from visionai.config.settings import Settings

    missing = tmp_path / "does-not-exist.gguf"
    monkeypatch.setattr(
        "visionai.app.get_settings",
        lambda: Settings(llm_provider="local", local_model_path=missing),
    )

    with pytest.raises(ValueError, match="Local model file not found"):
        app._build_llm_provider()


def test_build_llm_provider_local_with_a_real_file_builds_a_local_provider(
    monkeypatch, tmp_path
) -> None:
    from visionai.config.settings import Settings

    model_file = tmp_path / "model.gguf"
    model_file.write_text("not a real model, just a path that exists")

    class _FakeLocalProvider:
        def __init__(self, *, model_path: str) -> None:
            self.model_path = model_path

    monkeypatch.setattr(
        "visionai.app.get_settings",
        lambda: Settings(llm_provider="local", local_model_path=model_file),
    )
    monkeypatch.setattr(
        "visionai.intelligence.local_provider.LocalLlamaProvider", _FakeLocalProvider
    )

    provider = app._build_llm_provider()

    assert isinstance(provider, _FakeLocalProvider)
    assert provider.model_path == str(model_file)


def test_build_llm_provider_anthropic_without_a_key_raises(monkeypatch) -> None:
    from visionai.config.settings import Settings

    monkeypatch.setattr(
        "visionai.app.get_settings", lambda: Settings(llm_provider="anthropic")
    )
    monkeypatch.setattr("visionai.app.resolve_anthropic_api_key", lambda settings: None)

    with pytest.raises(ValueError, match="No Anthropic API key found"):
        app._build_llm_provider()


def test_build_llm_provider_anthropic_with_a_key_builds_the_real_provider(monkeypatch) -> None:
    from visionai.config.settings import Settings
    from visionai.intelligence.anthropic_provider import AnthropicProvider

    monkeypatch.setattr(
        "visionai.app.get_settings", lambda: Settings(llm_provider="anthropic")
    )
    monkeypatch.setattr("visionai.app.resolve_anthropic_api_key", lambda settings: "fake-key")

    provider = app._build_llm_provider()

    assert isinstance(provider, AnthropicProvider)


def test_app_suggest_uses_the_fallback_by_default(monkeypatch, capsys) -> None:
    launched: list[str] = []
    monkeypatch.setattr("sys.argv", ["visionai", "--suggest", "open notepad please"])
    monkeypatch.setattr(
        "visionai.app.build_runtime", lambda: build_runtime(launcher=launched.append)
    )

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "No LLM provider is configured" in output
    assert launched == []


def test_app_suggest_requires_confirmation_before_dispatch(monkeypatch, capsys) -> None:
    launched: list[str] = []

    class _FakeProvider:
        def respond(self, query: object) -> object:
            from visionai.intelligence import LLMReply

            return LLMReply(text="open notepad")

    monkeypatch.setattr("sys.argv", ["visionai", "--suggest", "can you open notepad"])
    monkeypatch.setattr("visionai.app._build_llm_provider", lambda: _FakeProvider())
    monkeypatch.setattr(
        "visionai.app.build_runtime", lambda: build_runtime(launcher=launched.append)
    )
    monkeypatch.setattr("builtins.input", lambda _: "yes")

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Proposed: Open notepad." in output
    assert "Opening notepad." in output
    assert launched == ["notepad.exe"]


def test_app_suggest_cancel_does_not_dispatch(monkeypatch, capsys) -> None:
    launched: list[str] = []

    class _FakeProvider:
        def respond(self, query: object) -> object:
            from visionai.intelligence import LLMReply

            return LLMReply(text="open notepad")

    monkeypatch.setattr("sys.argv", ["visionai", "--suggest", "can you open notepad"])
    monkeypatch.setattr("visionai.app._build_llm_provider", lambda: _FakeProvider())
    monkeypatch.setattr(
        "visionai.app.build_runtime", lambda: build_runtime(launcher=launched.append)
    )
    monkeypatch.setattr("builtins.input", lambda _: "no")

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Cancelled." in output
    assert launched == []


def test_app_suggest_reports_no_match(monkeypatch, capsys) -> None:
    launched: list[str] = []

    class _FakeProvider:
        def respond(self, query: object) -> object:
            from visionai.intelligence import LLMReply

            return LLMReply(text="NONE")

    monkeypatch.setattr("sys.argv", ["visionai", "--suggest", "order me a pizza"])
    monkeypatch.setattr("visionai.app._build_llm_provider", lambda: _FakeProvider())
    monkeypatch.setattr(
        "visionai.app.build_runtime", lambda: build_runtime(launcher=launched.append)
    )

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "No matching command found." in output
    assert launched == []


def test_app_suggest_asks_once_then_confirms_the_resolved_command(monkeypatch, capsys) -> None:
    launched: list[str] = []
    replies = iter(["CLARIFY: Which app should I open?", "open notepad"])

    class _FakeProvider:
        def respond(self, query: object) -> object:
            from visionai.intelligence import LLMReply

            return LLMReply(text=next(replies))

    monkeypatch.setattr("sys.argv", ["visionai", "--suggest", "open something"])
    monkeypatch.setattr("visionai.app._build_llm_provider", lambda: _FakeProvider())
    monkeypatch.setattr(
        "visionai.app.build_runtime", lambda: build_runtime(launcher=launched.append)
    )
    answers = iter(["notepad", "yes"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Which app should I open?" in output
    assert "Proposed: Open notepad." in output
    assert launched == ["notepad.exe"]


def test_app_rejects_unknown_text_command(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["visionai", "--text", "open calc & powershell"])

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "No executable action selected." in output


def test_app_runs_browser_search(monkeypatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr("sys.argv", ["visionai", "browser.search", "--query", "hello world"])
    monkeypatch.setattr(
        "visionai.capabilities.browser.webbrowser.open",
        lambda url: not opened.append(url),
    )

    exit_code = app.main()

    assert exit_code == 0
    assert opened == ["https://www.google.com/search?q=hello+world"]


def test_app_runs_media_control_with_injected_key_presser(monkeypatch) -> None:
    pressed: list[str] = []
    monkeypatch.setattr("sys.argv", ["visionai", "media.control", "--media-action", "mute"])
    monkeypatch.setattr(
        "visionai.app.build_runtime",
        lambda: build_runtime(key_presser=pressed.append),
    )

    exit_code = app.main()

    assert exit_code == 0
    assert pressed == ["volumemute"]


def test_app_blocks_mutating_capability_while_screen_is_locked(monkeypatch, capsys) -> None:
    """Proves the CLI dispatch path shares the runtime's live lock-state check,
    not a bare PolicyContext() independent of it."""
    monkeypatch.setattr("sys.argv", ["visionai", "app.open", "--app", "notepad"])
    monkeypatch.setattr(
        "visionai.app.build_runtime",
        lambda: build_runtime(lock_state=StaticLockStateAdapter(locked=True)),
    )

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "locked" in output


def test_app_rejects_unallowlisted_app_open_without_launching_anything(monkeypatch, capsys) -> None:
    """Safe to run for real: rejected before default_launcher is ever called."""
    monkeypatch.setattr("sys.argv", ["visionai", "app.open", "--app", "powershell"])

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "not an allowlisted application" in output


def test_app_routine_save_stores_a_valid_routine(monkeypatch, tmp_path, capsys) -> None:
    store = RoutineStore(tmp_path / "routines.json")
    monkeypatch.setattr(
        "sys.argv",
        ["visionai", "--routine-save", "morning", "what time is it", "open notepad"],
    )
    monkeypatch.setattr("visionai.app.default_routine_store", lambda: store)

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Routine 'morning' saved with 2 step(s)." in output
    assert store.get("morning") == ("what time is it", "open notepad")


def test_app_routine_save_rejects_an_unrecognized_phrase(monkeypatch, tmp_path, capsys) -> None:
    store = RoutineStore(tmp_path / "routines.json")
    monkeypatch.setattr(
        "sys.argv", ["visionai", "--routine-save", "morning", "order me a pizza"]
    )
    monkeypatch.setattr("visionai.app.default_routine_store", lambda: store)

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "Not a recognized command" in output
    assert store.get("morning") is None


def test_app_routine_save_rejects_a_sensitive_phrase(monkeypatch, tmp_path, capsys) -> None:
    store = RoutineStore(tmp_path / "routines.json")
    monkeypatch.setattr(
        "sys.argv", ["visionai", "--routine-save", "cleanup", "clear history"]
    )
    monkeypatch.setattr("visionai.app.default_routine_store", lambda: store)

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "may only contain read-only or reversible commands" in output
    assert store.get("cleanup") is None


def test_app_routine_run_executes_each_step_through_the_real_dispatcher(
    monkeypatch, tmp_path, capsys
) -> None:
    launched: list[str] = []
    store = RoutineStore(tmp_path / "routines.json")
    store.save("morning", ["open notepad"])
    monkeypatch.setattr("sys.argv", ["visionai", "--routine-run", "morning"])
    monkeypatch.setattr("visionai.app.default_routine_store", lambda: store)
    monkeypatch.setattr(
        "visionai.app.build_runtime", lambda: build_runtime(launcher=launched.append)
    )

    exit_code = app.main()

    assert exit_code == 0
    assert launched == ["notepad.exe"]


def test_app_routine_run_reports_an_unknown_routine(monkeypatch, tmp_path, capsys) -> None:
    store = RoutineStore(tmp_path / "routines.json")
    monkeypatch.setattr("sys.argv", ["visionai", "--routine-run", "does not exist"])
    monkeypatch.setattr("visionai.app.default_routine_store", lambda: store)

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "No saved routine named" in output


def test_app_routine_list_reports_saved_names(monkeypatch, tmp_path, capsys) -> None:
    store = RoutineStore(tmp_path / "routines.json")
    store.save("morning", ["what time is it"])
    monkeypatch.setattr("sys.argv", ["visionai", "--routine-list"])
    monkeypatch.setattr("visionai.app.default_routine_store", lambda: store)

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "morning" in output


def test_app_routine_list_reports_none_saved(monkeypatch, tmp_path, capsys) -> None:
    store = RoutineStore(tmp_path / "routines.json")
    monkeypatch.setattr("sys.argv", ["visionai", "--routine-list"])
    monkeypatch.setattr("visionai.app.default_routine_store", lambda: store)

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "No saved routines." in output


def test_app_routine_delete_removes_it(monkeypatch, tmp_path, capsys) -> None:
    store = RoutineStore(tmp_path / "routines.json")
    store.save("morning", ["what time is it"])
    monkeypatch.setattr("sys.argv", ["visionai", "--routine-delete", "morning"])
    monkeypatch.setattr("visionai.app.default_routine_store", lambda: store)

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "deleted" in output
    assert store.get("morning") is None
