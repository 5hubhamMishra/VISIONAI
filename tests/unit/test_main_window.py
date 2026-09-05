from threading import Event
from types import SimpleNamespace
from typing import Any

import pytest
from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon, QWidget

from visionai.capabilities import CapabilityManifest, CapabilityRegistry, IdempotencyMode
from visionai.capabilities.dispatcher import SerializedDispatcher
from visionai.config.secrets import InMemorySecretStore
from visionai.config.user_settings import UserSettingsStore
from visionai.core.cancellation import OperationController
from visionai.core.errors import StorageError
from visionai.core.event_bus import EventBus
from visionai.core.events import (
    ActionPlan,
    ActionRequest,
    ActionResult,
    Intent,
    RiskLevel,
)
from visionai.core.state import StateMachine
from visionai.intelligence import LLMReply
from visionai.observability import InMemoryAuditSink
from visionai.orchestration.event_orchestrator import EventOrchestrator
from visionai.platform.camera import GestureCandidate, StaticLandmarkAdapter
from visionai.policy import (
    ConfirmationService,
    FixedWindowRateLimiter,
    JsonPermissionStore,
    PolicyContext,
    PolicyEngine,
)
from visionai.recognition import TemporalGestureRecognizer
from visionai.runtime import build_runtime
from visionai.ui import main_window as main_window_module
from visionai.ui.main_window import MainWindow, _SettingsDialog


@pytest.mark.parametrize("failed", [False, True])
def test_completed_worker_has_exited_before_window_becomes_ready(
    qtbot: Any, monkeypatch: Any, failed: bool
) -> None:
    from visionai.ui.main_window import _RuntimeWorker

    def run(worker: _RuntimeWorker) -> None:
        if failed:
            worker.failed.emit("Simulated failure")
        else:
            worker.finished.emit([])
        # Keep the emitting thread alive long enough to expose early UI cleanup.
        QThread.msleep(100)

    monkeypatch.setattr(_RuntimeWorker, "run", run)
    window = MainWindow(build_runtime())
    qtbot.addWidget(window)
    window._command_input.setText("help")
    window.run_current_command()
    thread = window._worker_thread
    assert thread is not None
    exited = Event()
    thread.finished.connect(exited.set, Qt.ConnectionType.DirectConnection)
    try:
        _wait_for_command_complete(window, qtbot)
        assert exited.is_set()
    finally:
        if not exited.is_set():
            thread.quit()
            thread.wait(5000)


def _wait_for_command_complete(window: MainWindow, qtbot: Any) -> None:
    qtbot.waitUntil(
        lambda: not window._is_worker_running() and window._run_button.isEnabled(),
        timeout=5000,
    )


@pytest.mark.parametrize("quit_app", [False, True])
def test_window_waits_for_active_command_before_closing(
    qtbot: Any, monkeypatch: Any, quit_app: bool
) -> None:
    runtime = _build_slow_runtime()
    window = MainWindow(runtime)
    qtbot.addWidget(window)
    window.show()
    quit_calls: list[bool] = []
    monkeypatch.setattr(QApplication, "quit", lambda self: quit_calls.append(True))
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", lambda: False)
    window._command_input.setText("slow command")
    with qtbot.waitSignal(runtime.orchestrator.started, timeout=5000):
        window.run_current_command()
    try:
        if quit_app:
            window._quit_application()
            assert quit_calls == []
        else:
            assert not window.close()
            assert window.isVisible()
        assert not window.isEnabled()
        qtbot.waitUntil(lambda: window._worker_thread is None, timeout=5000)
        qtbot.waitUntil(
            lambda: bool(quit_calls) if quit_app else not window.isVisible(), timeout=5000
        )
    finally:
        runtime.operations.cancel_active_operation()
        qtbot.waitUntil(lambda: window._worker_thread is None, timeout=5000)


def test_clear_conversation_during_request_does_not_restore_deleted_memory(
    qtbot: Any, monkeypatch: Any
) -> None:
    started, release = Event(), Event()

    class Provider:
        def respond(self, query: Any) -> LLMReply:
            started.set()
            assert release.wait(5)
            return LLMReply(text="Late answer")

    window = MainWindow(build_runtime())
    qtbot.addWidget(window)
    monkeypatch.setattr("visionai.ui.main_window._build_llm_provider", Provider)
    monkeypatch.setattr(window, "_prompt_for_text", lambda *args: "Forget this question")
    window.show_ask_ai()
    try:
        qtbot.waitUntil(started.is_set, timeout=5000)
        window.clear_ask_conversation()
    finally:
        release.set()
        qtbot.waitUntil(lambda: window._ask_thread is None, timeout=5000)
    assert window._ask_memory.turns == ()


def test_closing_during_suggestion_never_prompts_or_executes(
    qtbot: Any, monkeypatch: Any
) -> None:
    started, release = Event(), Event()
    launched: list[str] = []

    class Provider:
        def respond(self, query: Any) -> LLMReply:
            started.set()
            assert release.wait(5)
            return LLMReply(text="open notepad")

    window = MainWindow(build_runtime(launcher=launched.append))
    qtbot.addWidget(window)
    window.show()
    monkeypatch.setattr("visionai.ui.main_window._build_llm_provider", Provider)
    monkeypatch.setattr(window, "_prompt_for_text", lambda *args: "open notepad")
    prompts: list[str] = []
    monkeypatch.setattr(window, "_ask_execute_confirmation", lambda text: prompts.append(text))
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", lambda: False)
    window.show_suggest_command()
    try:
        qtbot.waitUntil(started.is_set, timeout=5000)
        assert not window.close()
    finally:
        release.set()
        qtbot.waitUntil(lambda: window._suggest_thread is None, timeout=5000)
        qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)
    assert prompts == []
    assert launched == []


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


def _build_sensitive_runtime(
    calls: list[ActionRequest],
    tmp_path: Any,
    *,
    granted: bool = True,
) -> Any:
    registry = CapabilityRegistry([_sensitive_manifest()])
    audit = InMemoryAuditSink()
    permissions = JsonPermissionStore(tmp_path / "permissions.json")
    if granted:
        permissions.grant("test.sensitive")

    def handler(request: ActionRequest, cancellation: Any) -> ActionResult:
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
        permission_store=permissions,
        state_machine=state,
        policy_context_factory=lambda: PolicyContext(
            granted_capabilities=permissions.granted_capabilities()
        ),
    )
    return SimpleNamespace(
        audit=audit,
        operations=OperationController(),
        output_bus=output_bus,
        orchestrator=orchestrator,
        permissions=permissions,
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
    qtbot: Any, monkeypatch: Any, tmp_path: Any
) -> None:
    calls: list[ActionRequest] = []
    runtime = _build_sensitive_runtime(calls, tmp_path)
    window = MainWindow(runtime)
    qtbot.addWidget(window)
    monkeypatch.setattr(window, "_ask_confirmation", lambda confirmation: True)

    window._command_input.setText("do the sensitive thing")
    qtbot.mouseClick(window._run_button, Qt.MouseButton.LeftButton)
    _wait_for_command_complete(window, qtbot)

    assert len(calls) == 1, window._output.toPlainText()
    assert window._output.toPlainText() == "Sensitive action done."
    assert window._status_label.text() == "IDLE"
    assert window._history.count() == 1
    assert "[test.sensitive] Sensitive action done." in window._history.item(0).text()


def test_main_window_declining_confirmation_prevents_execution(
    qtbot: Any, monkeypatch: Any, tmp_path: Any
) -> None:
    calls: list[ActionRequest] = []
    runtime = _build_sensitive_runtime(calls, tmp_path)
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


def test_main_window_permission_prompt_then_confirmation_executes(
    qtbot: Any, monkeypatch: Any, tmp_path: Any
) -> None:
    calls: list[ActionRequest] = []
    runtime = _build_sensitive_runtime(calls, tmp_path, granted=False)
    window = MainWindow(runtime)
    qtbot.addWidget(window)
    monkeypatch.setattr(window, "_ask_permission", lambda permission: True)
    monkeypatch.setattr(window, "_ask_confirmation", lambda confirmation: True)

    window._command_input.setText("do the sensitive thing")
    qtbot.mouseClick(window._run_button, Qt.MouseButton.LeftButton)
    _wait_for_command_complete(window, qtbot)

    assert runtime.permissions.is_granted("test.sensitive") is True
    assert len(calls) == 1, window._output.toPlainText()
    assert window._output.toPlainText() == "Sensitive action done."
    assert window._status_label.text() == "IDLE"
    assert window._history.count() == 1


def test_main_window_declining_permission_prevents_grant_and_execution(
    qtbot: Any, monkeypatch: Any, tmp_path: Any
) -> None:
    calls: list[ActionRequest] = []
    runtime = _build_sensitive_runtime(calls, tmp_path, granted=False)
    window = MainWindow(runtime)
    qtbot.addWidget(window)
    monkeypatch.setattr(window, "_ask_permission", lambda permission: False)

    window._command_input.setText("do the sensitive thing")
    qtbot.mouseClick(window._run_button, Qt.MouseButton.LeftButton)
    _wait_for_command_complete(window, qtbot)

    assert runtime.permissions.is_granted("test.sensitive") is False
    assert calls == []
    assert window._output.toPlainText() == "Permission not granted."
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


def test_main_window_gesture_button_dispatches_mapped_command_and_stops_on_open_palm(
    qtbot: Any, monkeypatch: Any
) -> None:
    launched: list[str] = []
    runtime = build_runtime(launcher=launched.append)
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    candidates = [
        GestureCandidate(gesture_id="thumbs_up", hand="right", confidence=0.9),
        GestureCandidate(gesture_id="thumbs_up", hand="right", confidence=0.9),
        GestureCandidate(gesture_id="open_palm", hand="right", confidence=0.9),
        GestureCandidate(gesture_id="open_palm", hand="right", confidence=0.9),
    ]
    times = iter([0.0, 0.5, 0.6, 1.1])
    monkeypatch.setattr(
        "visionai.ui.main_window._build_landmark_adapter",
        lambda: StaticLandmarkAdapter(candidates=candidates),
    )
    monkeypatch.setattr(
        "visionai.ui.main_window.TemporalGestureRecognizer",
        lambda: TemporalGestureRecognizer(clock=lambda: next(times)),
    )

    qtbot.mouseClick(window._gesture_button, Qt.MouseButton.LeftButton)
    assert window._gesture_thread is not None

    qtbot.waitUntil(lambda: window._gesture_thread is None, timeout=5000)

    assert launched == ["notepad.exe"]
    assert window._output.toPlainText() == "Gesture control stopped. 2 gesture(s) confirmed."
    assert window._gesture_button.text() == "Start Gesture Control"
    assert window._gesture_button.isEnabled() is True
    assert window._history.count() >= 1


def test_main_window_gesture_button_can_be_cancelled_mid_session(
    qtbot: Any, monkeypatch: Any
) -> None:
    runtime = build_runtime()
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    monkeypatch.setattr(
        "visionai.ui.main_window._build_landmark_adapter",
        lambda: StaticLandmarkAdapter(candidates=[]),
    )

    qtbot.mouseClick(window._gesture_button, Qt.MouseButton.LeftButton)
    assert window._gesture_thread is not None

    qtbot.mouseClick(window._gesture_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window._gesture_thread is None, timeout=5000)

    assert window._output.toPlainText() == "Gesture control stopped. 0 gesture(s) confirmed."
    assert window._gesture_button.text() == "Start Gesture Control"
    assert window._gesture_button.isEnabled() is True


def test_main_window_gesture_button_reports_unavailable_webcam(
    qtbot: Any, monkeypatch: Any
) -> None:
    runtime = build_runtime()
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    def _broken_adapter() -> object:
        raise ImportError("mediapipe is not installed")

    monkeypatch.setattr("visionai.ui.main_window._build_landmark_adapter", _broken_adapter)

    qtbot.mouseClick(window._gesture_button, Qt.MouseButton.LeftButton)

    assert window._gesture_thread is None
    assert window._output.toPlainText() == "Gesture control unavailable: mediapipe is not installed"
    assert window._gesture_button.text() == "Start Gesture Control"


class _FakeMicrophoneCapture:
    """No real hardware: `stop()` returns nothing meaningful, since `transcribe` is faked too."""

    def start(self) -> None:
        pass

    def stop(self) -> None:
        return None


def test_main_window_gesture_button_closed_fist_starts_and_open_palm_sends_voice_command(
    qtbot: Any, monkeypatch: Any
) -> None:
    launched: list[str] = []
    runtime = build_runtime(launcher=launched.append)
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    candidates = [
        GestureCandidate(gesture_id="closed_fist", hand="right", confidence=0.9),
        GestureCandidate(gesture_id="closed_fist", hand="right", confidence=0.9),
        GestureCandidate(gesture_id="open_palm", hand="right", confidence=0.9),
        GestureCandidate(gesture_id="open_palm", hand="right", confidence=0.9),
    ]
    times = iter([0.0, 0.5, 0.6, 1.1])
    monkeypatch.setattr(
        "visionai.ui.main_window._build_landmark_adapter",
        lambda: StaticLandmarkAdapter(candidates=candidates),
    )
    monkeypatch.setattr(
        "visionai.ui.main_window.TemporalGestureRecognizer",
        lambda: TemporalGestureRecognizer(min_hold_ms=400, clock=lambda: next(times)),
    )
    monkeypatch.setattr(
        "visionai.ui.main_window._build_microphone_capture", lambda: _FakeMicrophoneCapture()
    )
    monkeypatch.setattr(
        "visionai.ui.main_window._build_transcriber", lambda: (lambda audio: "open notepad")
    )

    qtbot.mouseClick(window._gesture_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window._gesture_thread is None, timeout=5000)

    assert launched == ["notepad.exe"]
    assert window._output.toPlainText() == "Gesture control stopped. 2 gesture(s) confirmed."
    assert window._history.count() >= 1


def test_main_window_gesture_button_reports_when_voice_capture_is_unavailable(
    qtbot: Any, monkeypatch: Any
) -> None:
    launched: list[str] = []
    runtime = build_runtime(launcher=launched.append)
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    candidates = [
        GestureCandidate(gesture_id="closed_fist", hand="right", confidence=0.9),
        GestureCandidate(gesture_id="closed_fist", hand="right", confidence=0.9),
        GestureCandidate(gesture_id="open_palm", hand="right", confidence=0.9),
        GestureCandidate(gesture_id="open_palm", hand="right", confidence=0.9),
    ]
    times = iter([0.0, 0.5, 0.6, 1.1])

    def _broken_capture() -> object:
        raise OSError("no microphone device available")

    monkeypatch.setattr(
        "visionai.ui.main_window._build_landmark_adapter",
        lambda: StaticLandmarkAdapter(candidates=candidates),
    )
    monkeypatch.setattr(
        "visionai.ui.main_window.TemporalGestureRecognizer",
        lambda: TemporalGestureRecognizer(min_hold_ms=400, clock=lambda: next(times)),
    )
    monkeypatch.setattr("visionai.ui.main_window._build_microphone_capture", _broken_capture)

    qtbot.mouseClick(window._gesture_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window._gesture_thread is None, timeout=5000)

    assert launched == []
    assert window._output.toPlainText() == "Gesture control stopped. 2 gesture(s) confirmed."


def _wait_for_ask_complete(window: MainWindow, qtbot: Any) -> None:
    qtbot.waitUntil(lambda: window._ask_thread is None, timeout=5000)


def _wait_for_suggest_complete(window: MainWindow, qtbot: Any) -> None:
    qtbot.waitUntil(lambda: window._suggest_thread is None, timeout=5000)


class _FixedReplyProvider:
    def __init__(self, reply_text: str) -> None:
        self._reply_text = reply_text

    def respond(self, query: object) -> LLMReply:
        return LLMReply(text=self._reply_text)


def test_main_window_ask_ai_shows_the_llm_reply(qtbot: Any, monkeypatch: Any) -> None:
    runtime = build_runtime()
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    monkeypatch.setattr(window, "_prompt_for_text", lambda title, label: "what is 2+2?")
    monkeypatch.setattr(
        "visionai.ui.main_window._build_llm_provider", lambda: _FixedReplyProvider("four")
    )

    qtbot.mouseClick(window._ask_button, Qt.MouseButton.LeftButton)
    _wait_for_ask_complete(window, qtbot)

    assert window._output.toPlainText() == "four"
    assert window._ask_button.isEnabled() is True
    assert window._history.count() == 0


def test_main_window_ask_ai_cancel_does_nothing(qtbot: Any, monkeypatch: Any) -> None:
    runtime = build_runtime()
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    monkeypatch.setattr(window, "_prompt_for_text", lambda title, label: None)
    monkeypatch.setattr(
        "visionai.ui.main_window._build_llm_provider",
        lambda: pytest.fail("cancelling the dialog must not build a provider"),
    )

    qtbot.mouseClick(window._ask_button, Qt.MouseButton.LeftButton)

    assert window._ask_thread is None
    assert window._output.toPlainText() == ""


class _RecordingReplyProvider:
    """Records every query text it receives; replies in a fixed sequence."""

    def __init__(self, replies: list[str]) -> None:
        self.received_texts: list[str] = []
        self._replies = iter(replies)

    def respond(self, query: Any) -> LLMReply:
        self.received_texts.append(query.text)
        return LLMReply(text=next(self._replies))


def test_main_window_ask_ai_remembers_recent_turns_for_follow_up_questions(
    qtbot: Any, monkeypatch: Any
) -> None:
    runtime = build_runtime()
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    provider = _RecordingReplyProvider(["4", "6"])
    monkeypatch.setattr("visionai.ui.main_window._build_llm_provider", lambda: provider)

    monkeypatch.setattr(window, "_prompt_for_text", lambda title, label: "what is 2+2?")
    qtbot.mouseClick(window._ask_button, Qt.MouseButton.LeftButton)
    _wait_for_ask_complete(window, qtbot)
    assert window._output.toPlainText() == "4"

    monkeypatch.setattr(window, "_prompt_for_text", lambda title, label: "and 3+3?")
    qtbot.mouseClick(window._ask_button, Qt.MouseButton.LeftButton)
    _wait_for_ask_complete(window, qtbot)
    assert window._output.toPlainText() == "6"

    assert provider.received_texts == [
        "what is 2+2?",
        "User: what is 2+2?\nAssistant: 4\nUser: and 3+3?",
    ]


def test_main_window_clear_conversation_deletes_ask_ai_memory(
    qtbot: Any, monkeypatch: Any
) -> None:
    runtime = build_runtime()
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    provider = _RecordingReplyProvider(["4", "6"])
    monkeypatch.setattr("visionai.ui.main_window._build_llm_provider", lambda: provider)

    monkeypatch.setattr(window, "_prompt_for_text", lambda title, label: "what is 2+2?")
    qtbot.mouseClick(window._ask_button, Qt.MouseButton.LeftButton)
    _wait_for_ask_complete(window, qtbot)

    qtbot.mouseClick(window._clear_conversation_button, Qt.MouseButton.LeftButton)
    assert window._output.toPlainText() == "Ask AI conversation memory cleared."
    assert window._ask_memory.turns == ()

    monkeypatch.setattr(window, "_prompt_for_text", lambda title, label: "and 3+3?")
    qtbot.mouseClick(window._ask_button, Qt.MouseButton.LeftButton)
    _wait_for_ask_complete(window, qtbot)

    assert provider.received_texts == ["what is 2+2?", "and 3+3?"]


def test_main_window_ask_ai_failure_does_not_record_a_turn(qtbot: Any, monkeypatch: Any) -> None:
    runtime = build_runtime()
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    def _broken_provider() -> object:
        raise ValueError("no key configured")

    monkeypatch.setattr(window, "_prompt_for_text", lambda title, label: "what is 2+2?")
    monkeypatch.setattr("visionai.ui.main_window._build_llm_provider", _broken_provider)
    qtbot.mouseClick(window._ask_button, Qt.MouseButton.LeftButton)
    _wait_for_ask_complete(window, qtbot)

    assert window._ask_memory.turns == ()


def test_main_window_suggest_command_executes_after_confirmation(
    qtbot: Any, monkeypatch: Any
) -> None:
    launched: list[str] = []
    runtime = build_runtime(launcher=launched.append)
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    monkeypatch.setattr(window, "_prompt_for_text", lambda title, label: "open notepad please")
    monkeypatch.setattr(
        "visionai.ui.main_window._build_llm_provider",
        lambda: _FixedReplyProvider("open notepad"),
    )
    monkeypatch.setattr(window, "_ask_execute_confirmation", lambda summary: True)

    qtbot.mouseClick(window._suggest_button, Qt.MouseButton.LeftButton)
    _wait_for_suggest_complete(window, qtbot)

    assert window._output.toPlainText() == "Opening notepad."
    assert launched == ["notepad.exe"]
    assert window._suggest_button.isEnabled() is True
    assert window._history.count() == 1


def test_main_window_suggest_command_declined_does_not_execute(
    qtbot: Any, monkeypatch: Any
) -> None:
    launched: list[str] = []
    runtime = build_runtime(launcher=launched.append)
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    monkeypatch.setattr(window, "_prompt_for_text", lambda title, label: "open notepad please")
    monkeypatch.setattr(
        "visionai.ui.main_window._build_llm_provider",
        lambda: _FixedReplyProvider("open notepad"),
    )
    monkeypatch.setattr(window, "_ask_execute_confirmation", lambda summary: False)

    qtbot.mouseClick(window._suggest_button, Qt.MouseButton.LeftButton)
    _wait_for_suggest_complete(window, qtbot)

    assert window._output.toPlainText() == "Cancelled."
    assert launched == []
    assert window._suggest_button.isEnabled() is True
    assert window._history.count() == 0


def test_main_window_ask_ai_reports_a_provider_construction_failure(
    qtbot: Any, monkeypatch: Any
) -> None:
    runtime = build_runtime()
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    def _broken_provider() -> object:
        raise ValueError("VISIONAI_ANTHROPIC_API_KEY is not set")

    monkeypatch.setattr(window, "_prompt_for_text", lambda title, label: "what is 2+2?")
    monkeypatch.setattr("visionai.ui.main_window._build_llm_provider", _broken_provider)

    qtbot.mouseClick(window._ask_button, Qt.MouseButton.LeftButton)
    _wait_for_ask_complete(window, qtbot)

    assert (
        window._output.toPlainText()
        == "Could not get an answer: VISIONAI_ANTHROPIC_API_KEY is not set"
    )
    assert window._ask_button.isEnabled() is True


def test_main_window_suggest_command_reports_no_match(qtbot: Any, monkeypatch: Any) -> None:
    launched: list[str] = []
    runtime = build_runtime(launcher=launched.append)
    window = MainWindow(runtime)
    qtbot.addWidget(window)

    monkeypatch.setattr(window, "_prompt_for_text", lambda title, label: "order me a pizza")
    monkeypatch.setattr(
        "visionai.ui.main_window._build_llm_provider", lambda: _FixedReplyProvider("NONE")
    )

    qtbot.mouseClick(window._suggest_button, Qt.MouseButton.LeftButton)
    _wait_for_suggest_complete(window, qtbot)

    assert window._output.toPlainText() == "No matching command found."
    assert launched == []
    assert window._history.count() == 0


def test_build_llm_provider_none_returns_the_deterministic_fallback(monkeypatch: Any) -> None:
    from visionai.config.settings import Settings
    from visionai.intelligence import DeterministicFallbackProvider

    monkeypatch.setattr(
        "visionai.ui.main_window.get_settings", lambda: Settings(llm_provider="none")
    )

    provider = main_window_module._build_llm_provider()

    assert isinstance(provider, DeterministicFallbackProvider)


def test_build_llm_provider_local_without_a_configured_path_raises(monkeypatch: Any) -> None:
    from visionai.config.settings import Settings

    monkeypatch.setattr(
        "visionai.ui.main_window.get_settings", lambda: Settings(llm_provider="local")
    )

    with pytest.raises(ValueError, match="No local model path configured"):
        main_window_module._build_llm_provider()


def test_build_llm_provider_local_with_a_missing_file_raises(
    monkeypatch: Any, tmp_path: Any
) -> None:
    from visionai.config.settings import Settings

    missing = tmp_path / "does-not-exist.gguf"
    monkeypatch.setattr(
        "visionai.ui.main_window.get_settings",
        lambda: Settings(llm_provider="local", local_model_path=missing),
    )

    with pytest.raises(ValueError, match="Local model file not found"):
        main_window_module._build_llm_provider()


def test_build_llm_provider_local_with_a_real_file_builds_a_local_provider(
    monkeypatch: Any, tmp_path: Any
) -> None:
    from visionai.config.settings import Settings

    model_file = tmp_path / "model.gguf"
    model_file.write_text("not a real model, just a path that exists")

    class _FakeLocalProvider:
        def __init__(self, *, model_path: str) -> None:
            self.model_path = model_path

    monkeypatch.setattr(
        "visionai.ui.main_window.get_settings",
        lambda: Settings(llm_provider="local", local_model_path=model_file),
    )
    monkeypatch.setattr(
        "visionai.intelligence.local_provider.LocalLlamaProvider", _FakeLocalProvider
    )

    provider = main_window_module._build_llm_provider()

    assert isinstance(provider, _FakeLocalProvider)
    assert provider.model_path == str(model_file)


def test_build_llm_provider_anthropic_without_a_key_raises(monkeypatch: Any) -> None:
    from visionai.config.settings import Settings

    monkeypatch.setattr(
        "visionai.ui.main_window.get_settings", lambda: Settings(llm_provider="anthropic")
    )
    monkeypatch.setattr(
        "visionai.ui.main_window.resolve_anthropic_api_key", lambda settings: None
    )

    with pytest.raises(ValueError, match="No Anthropic API key found"):
        main_window_module._build_llm_provider()


def test_build_llm_provider_anthropic_with_a_key_builds_the_real_provider(
    monkeypatch: Any,
) -> None:
    from visionai.config.settings import Settings
    from visionai.intelligence.anthropic_provider import AnthropicProvider

    monkeypatch.setattr(
        "visionai.ui.main_window.get_settings", lambda: Settings(llm_provider="anthropic")
    )
    monkeypatch.setattr(
        "visionai.ui.main_window.resolve_anthropic_api_key", lambda settings: "fake-key"
    )

    provider = main_window_module._build_llm_provider()

    assert isinstance(provider, AnthropicProvider)


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
    assert "Voice input: available via Gesture Control and CLI wake-word listening" in text
    assert "Camera/vision input: available via the Gesture Control button" in text
    assert "LLM provider: none" in text
    assert "Ask AI conversation memory: 0 turn(s) retained this session" in text


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


def test_main_window_settings_text_reports_current_settings(qtbot: Any, tmp_path: Any) -> None:
    runtime = build_runtime()
    store = UserSettingsStore(tmp_path / "settings.json")
    window = MainWindow(runtime, settings_store=store)
    qtbot.addWidget(window)

    text = window._settings_text()

    assert "Log level: INFO" in text
    assert "Log directory: logs" in text
    assert "Data directory: .visionai" in text
    assert "Raw audio retention: disabled" in text
    assert "Raw camera retention: disabled" in text
    assert "Wake word: visionai" in text
    assert "Settings editing: log level, microphone selection, and wake word" in text


def test_main_window_settings_button_saves_a_chosen_log_level(
    qtbot: Any, monkeypatch: Any, tmp_path: Any
) -> None:
    runtime = build_runtime()
    store = UserSettingsStore(tmp_path / "settings.json")
    window = MainWindow(runtime, settings_store=store)
    qtbot.addWidget(window)

    monkeypatch.setattr(
        window,
        "_ask_new_settings",
        lambda current, device, devices, wake_word, api_key_configured=False: (
            "DEBUG",
            2,
            "friday",
            "",
            False,
        ),
    )
    configured: list[str] = []
    monkeypatch.setattr(
        "visionai.ui.main_window.configure_logging", lambda level: configured.append(level)
    )
    shown: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda parent, title, text: shown.append((title, text)),
    )

    qtbot.mouseClick(window._settings_button, Qt.MouseButton.LeftButton)

    assert store.get_log_level() == "DEBUG"
    assert configured == ["DEBUG"]
    assert store.get_microphone_device_index() == 2
    assert store.get_wake_word() == "friday"
    assert shown == [("Settings", "Settings saved.")]


def test_main_window_settings_button_does_nothing_when_dialog_is_cancelled(
    qtbot: Any, monkeypatch: Any, tmp_path: Any
) -> None:
    runtime = build_runtime()
    store = UserSettingsStore(tmp_path / "settings.json")
    window = MainWindow(runtime, settings_store=store)
    qtbot.addWidget(window)

    monkeypatch.setattr(
        window,
        "_ask_new_settings",
        lambda current, device, devices, wake_word, api_key_configured=False: None,
    )
    shown: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda parent, title, text: shown.append((title, text)),
    )

    qtbot.mouseClick(window._settings_button, Qt.MouseButton.LeftButton)

    assert store.get_log_level() is None
    assert shown == []


def test_main_window_settings_rejects_an_invalid_wake_word(
    qtbot: Any, monkeypatch: Any, tmp_path: Any
) -> None:
    runtime = build_runtime()
    store = UserSettingsStore(tmp_path / "settings.json")
    window = MainWindow(runtime, settings_store=store)
    qtbot.addWidget(window)

    monkeypatch.setattr(
        window,
        "_ask_new_settings",
        lambda current, device, devices, wake_word, api_key_configured=False: (
            "INFO",
            None,
            " ",
            "",
            False,
        ),
    )
    shown: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda parent, title, text: shown.append((title, text))
    )

    qtbot.mouseClick(window._settings_button, Qt.MouseButton.LeftButton)

    assert store.get_wake_word() is None
    assert shown == [("Settings", "wake word must be non-empty and contain no control characters")]


def test_settings_dialog_preselects_the_current_log_level(qtbot: Any) -> None:
    dialog = _SettingsDialog("WARNING", 2, [], wake_word="friday")
    qtbot.addWidget(dialog)

    assert dialog._log_level_combo.count() == 4
    assert dialog.selected_log_level() == "WARNING"
    assert dialog.selected_wake_word() == "friday"


def test_settings_dialog_preselects_a_listed_microphone(qtbot: Any) -> None:
    device = type("Device", (), {"index": 2, "name": "USB mic", "max_input_channels": 1})()
    dialog = _SettingsDialog("INFO", 2, [device], wake_word="visionai")
    qtbot.addWidget(dialog)

    assert dialog.selected_microphone_device_index() == 2


def test_settings_dialog_reports_api_key_status(qtbot: Any) -> None:
    unset = _SettingsDialog("INFO", None, [], wake_word="visionai", api_key_configured=False)
    qtbot.addWidget(unset)
    configured = _SettingsDialog("INFO", None, [], wake_word="visionai", api_key_configured=True)
    qtbot.addWidget(configured)

    assert unset._api_key_status_label.text() == "Anthropic API key: not set"
    assert configured._api_key_status_label.text() == "Anthropic API key: configured"
    assert unset.entered_api_key() == ""
    assert unset.clear_api_key_requested() is False


def test_main_window_settings_button_stores_a_new_api_key(
    qtbot: Any, monkeypatch: Any, tmp_path: Any
) -> None:
    runtime = build_runtime()
    store = UserSettingsStore(tmp_path / "settings.json")
    window = MainWindow(runtime, settings_store=store)
    qtbot.addWidget(window)
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)

    secret_store = InMemorySecretStore()
    monkeypatch.setattr("visionai.ui.main_window.default_secret_store", lambda: secret_store)
    monkeypatch.setattr(
        window,
        "_ask_new_settings",
        lambda current, device, devices, wake_word, api_key_configured=False: (
            "INFO",
            None,
            "visionai",
            "sk-ant-fake-key",
            False,
        ),
    )

    qtbot.mouseClick(window._settings_button, Qt.MouseButton.LeftButton)

    assert secret_store.get("anthropic_api_key") == "sk-ant-fake-key"


def test_main_window_settings_button_clears_the_stored_api_key(
    qtbot: Any, monkeypatch: Any, tmp_path: Any
) -> None:
    runtime = build_runtime()
    store = UserSettingsStore(tmp_path / "settings.json")
    window = MainWindow(runtime, settings_store=store)
    qtbot.addWidget(window)
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)

    secret_store = InMemorySecretStore()
    secret_store.set("anthropic_api_key", "sk-ant-fake-key")
    monkeypatch.setattr("visionai.ui.main_window.default_secret_store", lambda: secret_store)
    monkeypatch.setattr(
        window,
        "_ask_new_settings",
        lambda current, device, devices, wake_word, api_key_configured=False: (
            "INFO",
            None,
            "visionai",
            "",
            True,
        ),
    )

    qtbot.mouseClick(window._settings_button, Qt.MouseButton.LeftButton)

    assert secret_store.get("anthropic_api_key") is None


def test_main_window_settings_button_reports_a_key_storage_failure(
    qtbot: Any, monkeypatch: Any, tmp_path: Any
) -> None:
    runtime = build_runtime()
    store = UserSettingsStore(tmp_path / "settings.json")
    window = MainWindow(runtime, settings_store=store)
    qtbot.addWidget(window)

    class _FailingSecretStore:
        def set(self, key: str, value: str) -> None:
            raise StorageError("keychain unavailable")

    monkeypatch.setattr(
        "visionai.ui.main_window.default_secret_store", lambda: _FailingSecretStore()
    )
    monkeypatch.setattr(
        window,
        "_ask_new_settings",
        lambda current, device, devices, wake_word, api_key_configured=False: (
            "INFO",
            None,
            "visionai",
            "sk-ant-fake-key",
            False,
        ),
    )
    shown: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda parent, title, text: shown.append((title, text))
    )

    qtbot.mouseClick(window._settings_button, Qt.MouseButton.LeftButton)

    assert shown == [("Settings", "Could not store the key: keychain unavailable")]
    assert store.get_log_level() is None


def test_settings_remains_usable_without_keyring(
    qtbot: Any, monkeypatch: Any, tmp_path: Any
) -> None:
    store = UserSettingsStore(tmp_path / "settings.json")
    window = MainWindow(build_runtime(), settings_store=store)
    qtbot.addWidget(window)

    def unavailable(*args: Any) -> None:
        raise ImportError("keyring is not installed")

    monkeypatch.setattr("visionai.ui.main_window.resolve_anthropic_api_key", unavailable)
    shown: list[bool] = []
    monkeypatch.setattr(
        window, "_ask_new_settings", lambda *args: shown.append(args[-1])
    )
    window.show_settings()
    assert shown == [False]


def test_settings_rejects_conflicting_key_changes(
    qtbot: Any, monkeypatch: Any, tmp_path: Any
) -> None:
    store = UserSettingsStore(tmp_path / "settings.json")
    window = MainWindow(build_runtime(), settings_store=store)
    qtbot.addWidget(window)
    monkeypatch.setattr("visionai.ui.main_window.resolve_anthropic_api_key", lambda *args: None)
    monkeypatch.setattr(
        window, "_ask_new_settings", lambda *args: ("DEBUG", None, "friday", "new-key", True)
    )
    warnings: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text: warnings.append(text))
    monkeypatch.setattr(
        "visionai.ui.main_window.default_secret_store",
        lambda: pytest.fail("conflicting choices must not touch the keychain"),
    )
    window.show_settings()
    assert warnings == ["Choose either a new key or clear stored key."]
    assert store.get_wake_word() is None
    assert store.get_log_level() is None


def test_main_window_shows_onboarding_once(qtbot: Any, monkeypatch: Any, tmp_path: Any) -> None:
    runtime = build_runtime()
    store = UserSettingsStore(tmp_path / "settings.json")
    window = MainWindow(runtime, settings_store=store)
    qtbot.addWidget(window)

    shown: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda parent, title, text: shown.append((title, text)),
    )

    window.maybe_show_onboarding()
    window.maybe_show_onboarding()

    assert len(shown) == 1
    assert shown[0][0] == "Welcome to VisionAI"
    assert store.has_seen_onboarding() is True


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
        window._gesture_button,
        window._ask_button,
        window._suggest_button,
        window._clear_conversation_button,
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
        window._clear_conversation_button,
        window._suggest_button,
        window._ask_button,
        window._gesture_button,
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
