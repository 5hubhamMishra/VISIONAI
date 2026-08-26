from visionai import app
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


def test_app_rejects_unallowlisted_app_open_without_launching_anything(monkeypatch, capsys) -> None:
    """Safe to run for real: rejected before default_launcher is ever called."""
    monkeypatch.setattr("sys.argv", ["visionai", "app.open", "--app", "powershell"])

    exit_code = app.main()
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "not an allowlisted application" in output
