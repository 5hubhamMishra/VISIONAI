import pytest

from visionai import app
from visionai.platform.lock_state import StaticLockStateAdapter
from visionai.platform.microphone import MicrophoneDevice
from visionai.runtime import build_runtime


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
