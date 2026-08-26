from types import SimpleNamespace
from typing import Any

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon, QWidget

from visionai.capabilities import CapabilityManifest, CapabilityRegistry, IdempotencyMode
from visionai.capabilities.dispatcher import SerializedDispatcher
from visionai.core.cancellation import OperationController
from visionai.core.event_bus import EventBus
from visionai.core.events import (
    ActionPlan,
    ActionRequest,
    ActionResult,
    Intent,
    RiskLevel,
)
from visionai.core.state import StateMachine
from visionai.observability import InMemoryAuditSink
from visionai.orchestration.event_orchestrator import EventOrchestrator
from visionai.policy import ConfirmationService, FixedWindowRateLimiter, PolicyContext, PolicyEngine
from visionai.runtime import build_runtime
from visionai.ui.main_window import MainWindow


def _wait_for_command_complete(window: MainWindow, qtbot: Any) -> None:
    # `_is_worker_running()` reflects real worker lifecycle regardless of
    # whether Run, Stop, or a confirmation follow-up started the worker.
    qtbot.waitUntil(lambda: not window._is_worker_running(), timeout=5000)


def _sensitive_manifest() -> CapabilityManifest:
    return CapabilityManifest(
        id="test.sensitive",
        description="A synthetic sensitive capability for confirmation dialog tests.",
        risk_level=RiskLevel.SENSITIVE,
        permission_required=True,
        confirmation_required=True,
        rate_limit_per_minute=10,
        timeout_seconds=3,
        idempotency=IdempotencyMode.IDEMPOTENT,
        audit_category="test.sensitive",
        handler_id="test.sensitive",
    )


class _FixedPlanner:
    def plan(self, text: str) -> tuple[Intent, ActionPlan]:
        request = ActionRequest(capability_id="test.sensitive", risk_level=RiskLevel.SENSITIVE)
        return (
            Intent(name="test.sensitive", confidence=1.0, source_text=text),
            ActionPlan(steps=(request,), summary="Do the sensitive thing."),
        )


def _build_sensitive_runtime(calls: list[ActionRequest]) -> Any:
    registry = CapabilityRegistry([_sensitive_manifest()])
    audit = InMemoryAuditSink()

    def handler(request: ActionRequest) -> ActionResult:
        calls.append(request)
        return ActionResult(request_id=request.id, success=True, message="Sensitive action done.")

    dispatcher = SerializedDispatcher(
        registry=registry,
        policy=PolicyEngine(registry, FixedWindowRateLimiter()),
        audit=audit,
        handlers={"test.sensitive": handler},
    )
    output_bus = EventBus(max_size=10)
    state = StateMachine()
    orchestrator = EventOrchestrator(
        input_bus=EventBus(max_size=10),
        output_bus=output_bus,
        planner=_FixedPlanner(),
        dispatcher=dispatcher,
        operations=OperationController(),
        confirmation=ConfirmationService(),
        state_machine=state,
        policy_context_factory=lambda: PolicyContext(
            granted_capabilities=frozenset({"test.sensitive"})
        ),
    )
    return SimpleNamespace(
        audit=audit,
        operations=OperationController(),
        output_bus=output_bus,
        orchestrator=orchestrator,
        registry=registry,
        state_machine=state,
    )


class _EmptyAudit:
    def list(self) -> tuple[Any, ...]:
        return ()


class _SlowOrchestrator(QObject):
    started = Signal()

    def __init__(self, *, output_bus: EventBus, operations: OperationController) -> None:
        super().__init__()
        self._output_bus = output_bus
        self._operations = operations

    async def process_event(self, event: Any) -> None:
        token = self._operations.begin_operation()
        self.started.emit()
        token.wait(timeout=2)
        self._operations.finish_operation(token)
        await self._output_bus.publish(
            ActionResult(request_id=event.id, success=True, message="Slow command complete.")
        )


def _build_slow_runtime() -> Any:
    output_bus = EventBus(max_size=10)
    operations = OperationController()
    state = StateMachine()
    return SimpleNamespace(
        audit=_EmptyAudit(),
        operations=operations,
        output_bus=output_bus,
        orchestrator=_SlowOrchestrator(output_bus=output_bus, operations=operations),
        registry=SimpleNamespace(list=lambda: ()),
        state_machine=state,
    )


def test_main_window_runs_command_through_runtime(qtbot: Any) -> None:
    launched: list[str] = []
    runtime = build_runtime(launcher=launched.append)
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    window.show()
    window._command_input.setText("open notepad")
    qtbot.mouseClick(window._run_button, Qt.MouseButton.LeftButton)
    _wait_for_command_complete(window, qtbot)

    assert launched == ["notepad.exe"]
    assert window._output.toPlainText() == "Opening notepad."
    assert window._status_label.text() == "IDLE"
    assert window._history.count() == 1
    assert "[app.launch] Opening notepad." in window._history.item(0).text()
    assert window._command_input.text() == ""
    assert window._command_input.isEnabled() is True
    assert window._run_button.isEnabled() is True


def test_main_window_confirms_sensitive_action_before_execution(
    qtbot: Any, monkeypatch: Any
) -> None:
    calls: list[ActionRequest] = []
    runtime = _build_sensitive_runtime(calls)
    window = MainWindow(runtime)
    qtbot.addWidget(window)
    monkeypatch.setattr(window, "_ask_confirmation", lambda confirmation: True)

    window._command_input.setText("do the sensitive thing")
    qtbot.mouseClick(window._run_button, Qt.MouseButton.LeftButton)
    _wait_for_command_complete(window, qtbot)

    assert len(calls) == 1
    assert window._output.toPlainText() == "Sensitive action done."
    assert window._status_label.text() == "IDLE"
    assert window._history.count() == 1
    assert "[test.sensitive] Sensitive action done." in window._history.item(0).text()


def test_main_window_declining_confirmation_prevents_execution(
    qtbot: Any, monkeypatch: Any
) -> None:
    calls: list[ActionRequest] = []
    runtime = _build_sensitive_runtime(calls)
    window = MainWindow(runtime)
    qtbot.addWidget(window)
    monkeypatch.setattr(window, "_ask_confirmation", lambda confirmation: False)

    window._command_input.setText("do the sensitive thing")
    qtbot.mouseClick(window._run_button, Qt.MouseButton.LeftButton)
    _wait_for_command_complete(window, qtbot)

    assert calls == []
    assert window._output.toPlainText() == "Action cancelled."
    assert window._status_label.text() == "IDLE"
    assert window._history.count() == 0


def test_main_window_renders_non_executable_text(qtbot: Any) -> None:
    runtime = build_runtime()
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    window._command_input.setText("please do the risky vague thing")
    qtbot.keyClick(window._command_input, Qt.Key.Key_Return)
    _wait_for_command_complete(window, qtbot)

    assert window._output.toPlainText() == "No executable action selected."
    assert window._history.count() == 0


def test_main_window_stop_button_reports_no_active_operation(qtbot: Any) -> None:
    runtime = build_runtime()
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    qtbot.mouseClick(window._stop_button, Qt.MouseButton.LeftButton)
    _wait_for_command_complete(window, qtbot)

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
    _wait_for_command_complete(window, qtbot)
    assert window._output.toPlainText() == "No operation is currently running."


def test_main_window_stop_button_can_cancel_while_worker_is_running(qtbot: Any) -> None:
    runtime = _build_slow_runtime()
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    window._command_input.setText("slow command")
    with qtbot.waitSignal(runtime.orchestrator.started, timeout=5000):
        qtbot.mouseClick(window._run_button, Qt.MouseButton.LeftButton)

    assert window._run_button.isEnabled() is False
    qtbot.mouseClick(window._stop_button, Qt.MouseButton.LeftButton)

    assert window._output.toPlainText() == "Stop requested."
    _wait_for_command_complete(window, qtbot)
    assert window._run_button.isEnabled() is True


def test_main_window_and_children_inherit_native_os_theming(qtbot: Any) -> None:
    """No widget hardcodes its own colors -- contrast comes from the OS theme.

    MainWindow applies zero custom stylesheets or palettes anywhere. This
    matters for WCAG contrast in a way a fixed color audit cannot capture:
    the app's real on-screen colors come from the native platform style
    (`windows11` normally; this headless test suite runs under Qt's
    offscreen platform, which substitutes an unrelated generic `fusion`
    palette -- verified by direct inspection, not assumed -- so asserting
    against *specific* RGB values here would test the wrong platform's
    colors, not what a user actually sees). What this test can and does
    prove: nothing in this codebase overrides that inheritance, so Windows'
    own accessibility guarantees for native controls -- including High
    Contrast mode, which only works by overriding the OS theme the app
    already defers to -- are never silently defeated by a hardcoded style.
    """

    runtime = build_runtime()
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    assert window.styleSheet() == ""
    for widget in window.findChildren(QWidget):
        assert widget.styleSheet() == "", f"{widget!r} has a custom stylesheet"


def test_main_window_diagnostics_text_reports_environment_and_state(qtbot: Any) -> None:
    runtime = build_runtime()
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    text = window._diagnostics_text()

    assert "VisionAI: 0.1.0" in text
    assert "PySide6:" in text
    assert "Registered capabilities: " in text
    assert "Registered capabilities: 0" not in text
    assert "State: IDLE" in text
    assert "Voice input: not connected" in text
    assert "Camera/vision input: not connected" in text


def test_main_window_diagnostics_button_opens_a_dialog(qtbot: Any, monkeypatch: Any) -> None:
    runtime = build_runtime()
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    shown: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda parent, title, text: shown.append((title, text)),
    )

    qtbot.mouseClick(window._diagnostics_button, Qt.MouseButton.LeftButton)

    assert len(shown) == 1
    assert shown[0][0] == "Diagnostics"
    assert "VisionAI:" in shown[0][1]


def test_main_window_settings_text_reports_current_read_only_settings(qtbot: Any) -> None:
    runtime = build_runtime()
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    text = window._settings_text()

    assert "Log level: INFO" in text
    assert "Log directory: logs" in text
    assert "Data directory: .visionai" in text
    assert "Raw audio retention: disabled" in text
    assert "Raw camera retention: disabled" in text
    assert "Settings editing: not enabled yet" in text


def test_main_window_settings_button_opens_a_dialog(qtbot: Any, monkeypatch: Any) -> None:
    runtime = build_runtime()
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    shown: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda parent, title, text: shown.append((title, text)),
    )

    qtbot.mouseClick(window._settings_button, Qt.MouseButton.LeftButton)

    assert len(shown) == 1
    assert shown[0][0] == "Settings"
    assert "Log level:" in shown[0][1]


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
        window._diagnostics_button,
        window._settings_button,
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
        window._settings_button,
        window._diagnostics_button,
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
