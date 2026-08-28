from dataclasses import dataclass, field

import pytest

from visionai import app
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
