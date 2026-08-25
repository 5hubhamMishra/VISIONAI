from visionai import app


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
