from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from visionai.runtime import build_runtime
from visionai.ui.main_window import MainWindow


def test_main_window_runs_command_through_runtime(qtbot: Any) -> None:
    launched: list[str] = []
    runtime = build_runtime(launcher=launched.append)
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    window.show()
    window._command_input.setText("open notepad")
    qtbot.mouseClick(window._run_button, Qt.MouseButton.LeftButton)

    assert launched == ["notepad.exe"]
    assert window._output.toPlainText() == "Opening notepad."
    assert window._status_label.text() == "IDLE"
    assert window._history.count() == 1
    assert "[app.launch] Opening notepad." in window._history.item(0).text()
    assert window._command_input.text() == ""
    assert window._command_input.isEnabled() is True
    assert window._run_button.isEnabled() is True


def test_main_window_renders_non_executable_text(qtbot: Any) -> None:
    runtime = build_runtime()
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    window._command_input.setText("please do the risky vague thing")
    qtbot.keyClick(window._command_input, Qt.Key.Key_Return)

    assert window._output.toPlainText() == "No executable action selected."
    assert window._history.count() == 0


def test_main_window_stop_button_reports_no_active_operation(qtbot: Any) -> None:
    runtime = build_runtime()
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    qtbot.mouseClick(window._stop_button, Qt.MouseButton.LeftButton)

    assert window._output.toPlainText() == "No operation is currently running."
    assert window._status_label.text() == "IDLE"
    assert window._history.count() == 1
    assert "[system.control]" in window._history.item(0).text()


def test_main_window_stop_button_is_independent_of_run_state(qtbot: Any) -> None:
    runtime = build_runtime()
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    window._command_input.setEnabled(False)
    window._run_button.setEnabled(False)

    assert window._stop_button.isEnabled() is True
    qtbot.mouseClick(window._stop_button, Qt.MouseButton.LeftButton)
    assert window._output.toPlainText() == "No operation is currently running."


def test_main_window_tab_order_reaches_every_control_without_a_trap(qtbot: Any) -> None:
    runtime = build_runtime()
    window = MainWindow(runtime)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    assert window.focusWidget() is window._command_input

    expected_order = [
        window._run_button,
        window._stop_button,
        window._output,
        window._history,
        window._command_input,
    ]
    for widget in expected_order:
        qtbot.keyClick(window.focusWidget(), Qt.Key.Key_Tab)
        assert window.focusWidget() is widget


def test_main_window_tab_order_reverses_cleanly_with_shift_tab(qtbot: Any) -> None:
    runtime = build_runtime()
    window = MainWindow(runtime)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    expected_reverse_order = [
        window._history,
        window._output,
        window._stop_button,
        window._run_button,
        window._command_input,
    ]
    for widget in expected_reverse_order:
        qtbot.keyClick(window.focusWidget(), Qt.Key.Key_Backtab)
        assert window.focusWidget() is widget


def test_main_window_tray_menu_has_show_and_quit_actions(qtbot: Any) -> None:
    runtime = build_runtime()
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    assert [action.text() for action in window._tray_menu.actions()] == [
        "Show VisionAI",
        "Quit",
    ]


def test_main_window_tray_show_action_shows_and_raises_hidden_window(qtbot: Any) -> None:
    runtime = build_runtime()
    window = MainWindow(runtime)
    qtbot.addWidget(window)
    window.hide()

    window._show_action.trigger()

    assert window.isVisible() is True


def test_main_window_tray_quit_action_quits_the_application(
    qtbot: Any, monkeypatch: Any
) -> None:
    runtime = build_runtime()
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    quit_calls: list[bool] = []
    monkeypatch.setattr(QApplication, "quit", lambda self: quit_calls.append(True))

    window._quit_action.trigger()

    assert quit_calls == [True]


def test_main_window_tray_trigger_toggles_visibility(qtbot: Any) -> None:
    runtime = build_runtime()
    window = MainWindow(runtime)
    qtbot.addWidget(window)
    window.show()

    window._on_tray_activated(QSystemTrayIcon.ActivationReason.Trigger)
    assert window.isVisible() is False

    window._on_tray_activated(QSystemTrayIcon.ActivationReason.Trigger)
    assert window.isVisible() is True


def test_main_window_close_minimizes_to_tray_when_available(
    qtbot: Any, monkeypatch: Any
) -> None:
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True))
    runtime = build_runtime()
    window = MainWindow(runtime)
    qtbot.addWidget(window)
    window.show()

    event = QCloseEvent()
    window.closeEvent(event)

    assert event.isAccepted() is False
    assert window.isVisible() is False


def test_main_window_close_exits_normally_when_tray_unavailable(qtbot: Any) -> None:
    # QSystemTrayIcon.isSystemTrayAvailable() is False under the offscreen
    # platform this test suite runs under, so this exercises the real
    # fallback rather than a mocked one -- see tests/conftest.py.
    runtime = build_runtime()
    window = MainWindow(runtime)
    qtbot.addWidget(window)
    window.show()

    event = QCloseEvent()
    window.closeEvent(event)

    assert event.isAccepted() is True


def test_main_window_ignores_empty_input(qtbot: Any) -> None:
    runtime = build_runtime()
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    window._command_input.setText("   ")
    qtbot.mouseClick(window._run_button, Qt.MouseButton.LeftButton)

    assert window._output.toPlainText() == ""
    assert window._history.count() == 0
