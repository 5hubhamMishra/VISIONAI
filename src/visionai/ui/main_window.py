"""Minimal desktop main window: a thin front end over the safe runtime.

This is the Phase 2 slice, not the full main window described in Section 14
of the master prompt. It exists to prove the UI can drive the
already-tested orchestrator/state machine/dispatcher path safely, not to
be a finished product. Every typed command is turned into a final
TranscriptEvent and handed to the same `EventOrchestrator` the CLI and
automated tests use -- this window adds no new planning or execution logic
of its own. The tray icon (show/hide, quit), diagnostics view, settings
(log level only), and the one-time onboarding dialog are the exceptions:
they are pure window-lifecycle/read-only-introspection/local-preference
controls with no path into policy, permissions, or dispatch.
"""

from __future__ import annotations

import asyncio
import sys
import traceback
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

import PySide6
from pydantic import ValidationError
from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStyle,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import visionai
from visionai.config import (
    default_secret_store,
    default_user_settings_store,
    effective_log_level,
    get_settings,
    resolve_anthropic_api_key,
)
from visionai.config.settings import LogLevel
from visionai.config.user_settings import UserSettingsStore, effective_wake_word
from visionai.core.cancellation import CancellationToken
from visionai.core.errors import ProviderError, StorageError
from visionai.core.event_bus import EventBus
from visionai.core.events import (
    ActionPlan,
    ActionResult,
    ConfirmationRequest,
    ErrorEvent,
    EventBase,
    GestureEvent,
    PermissionRequest,
    TranscriptEvent,
)
from visionai.intelligence import (
    ConversationMemory,
    DeterministicFallbackProvider,
    LLMProvider,
    LLMQuery,
    suggest_command_result,
)
from visionai.observability import configure_logging
from visionai.orchestration.event_orchestrator import InputAdapter
from visionai.platform.camera import LandmarkAdapter
from visionai.recognition import GestureCaptureLoop, GestureListeningLoop, TemporalGestureRecognizer
from visionai.runtime import Runtime, build_runtime

_LOG_LEVELS: tuple[LogLevel, ...] = ("DEBUG", "INFO", "WARNING", "ERROR")

_ONBOARDING_TEXT = (
    "VisionAI is a local desktop assistant. Every command you type is checked "
    "by the same safety policy the console uses before anything runs:\n\n"
    "- Read-only actions (time, battery, capability list) run immediately.\n"
    "- Sensitive actions ask you to grant permission once.\n"
    "- Actions with side effects ask you to confirm each time, showing exactly "
    "what will happen.\n\n"
    "Use Stop to cancel a running action, Diagnostics to check runtime status, "
    "and Settings to change the log level. Gesture Control watches your webcam "
    "and dispatches recognized hand gestures through those same safety checks. "
    "Ask AI sends a question to a configured LLM provider (off by default) and "
    "only shows the answer, remembering recent questions/answers from this "
    "session only (never saved to disk) so follow-up questions have context; "
    "Clear Conversation deletes that memory. Suggest Command asks the LLM to "
    "propose a command and still asks you to confirm before running anything. "
    "This dialog only shows once."
)

if TYPE_CHECKING:
    import numpy as np
    from PySide6.QtGui import QCloseEvent

    from visionai.orchestration.microphone_capture import MicrophonePushToTalk
    from visionai.platform.microphone import MicrophoneCapture, MicrophoneDevice
    from visionai.platform.webcam import WebcamLandmarkAdapter


def _build_landmark_adapter() -> WebcamLandmarkAdapter:
    """Build the real webcam/mediapipe adapter, mirroring `app._build_landmark_adapter`.

    A free module-level function (not inlined) so tests can inject a
    `StaticLandmarkAdapter` the same way `visionai.app`'s tests do, with no
    real camera or the `vision` extra required.
    """

    from visionai.platform.webcam import WebcamLandmarkAdapter

    return WebcamLandmarkAdapter()


def _build_gesture_cancellation_token() -> CancellationToken:
    return CancellationToken()


def _build_microphone_capture() -> MicrophoneCapture:
    """Mirrors `app._build_microphone_capture`, injectable the same way."""

    from visionai.platform.microphone import default_microphone_capture

    return default_microphone_capture()


def _build_transcriber() -> Callable[[np.ndarray], str]:
    """Mirrors `app._build_transcriber`, injectable the same way."""

    from visionai.platform.stt import default_transcriber

    return default_transcriber()


def _build_llm_provider() -> LLMProvider:
    """Mirrors `app._build_llm_provider`, injectable the same way."""

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


class _RuntimeWorker(QObject):
    """Run one runtime operation off the GUI thread."""

    finished = Signal(list)
    failed = Signal(str)

    def __init__(
        self,
        *,
        runtime: Runtime,
        text: str | None = None,
        confirmation: ConfirmationRequest | None = None,
        permission: PermissionRequest | None = None,
    ) -> None:
        super().__init__()
        self._runtime = runtime
        self._text = text
        self._confirmation = confirmation
        self._permission = permission

    @Slot()
    def run(self) -> None:
        try:
            if self._permission is not None:
                outputs = asyncio.run(_grant_runtime_permission(self._runtime, self._permission))
            elif self._confirmation is not None:
                outputs = asyncio.run(_confirm_runtime_request(self._runtime, self._confirmation))
            elif self._text is not None:
                outputs = asyncio.run(_process_runtime_text(self._runtime, self._text))
            else:
                outputs = []
        except Exception as exc:  # pragma: no cover - defensive GUI boundary
            self.failed.emit("".join(traceback.format_exception(exc)))
            return
        self.finished.emit(outputs)


async def _process_runtime_text(runtime: Runtime, text: str) -> list[EventBase]:
    event = TranscriptEvent(text=text, confidence=1.0, language="en", is_final=True)
    await runtime.orchestrator.process_event(event)
    return await _drain_runtime_outputs(runtime)


async def _confirm_runtime_request(
    runtime: Runtime, confirmation: ConfirmationRequest
) -> list[EventBase]:
    await runtime.orchestrator.confirm(confirmation.id)
    return await _drain_runtime_outputs(runtime)


async def _grant_runtime_permission(
    runtime: Runtime, permission: PermissionRequest
) -> list[EventBase]:
    await runtime.orchestrator.grant_permission(permission.id)
    return await _drain_runtime_outputs(runtime)


async def _drain_runtime_outputs(runtime: Runtime) -> list[EventBase]:
    outputs: list[EventBase] = []
    while runtime.output_bus.size:
        outputs.append(await runtime.output_bus.next_event())
    return outputs


class _GestureListenWorker(QObject):
    """Run a continuous `GestureListeningLoop` off the GUI thread.

    Mirrors `app._run_gesture_listen`'s worker-thread/asyncio session shape:
    a real camera has no natural end, so this only ever stops via the
    `CancellationToken` the caller cancels (the Gesture Control button, or
    the loop's own "open_palm" stop gesture). Confirmed gestures still only
    ever reach the runtime as a `GestureEvent` through the real
    `InputAdapter`/orchestrator/dispatcher path -- this worker adds no
    planning or dispatch logic of its own, same as `_RuntimeWorker`.
    """

    gesture_confirmed = Signal(str)
    dispatched = Signal(str)
    finished = Signal(int)
    failed = Signal(str)

    def __init__(
        self,
        *,
        runtime: Runtime,
        landmark_adapter: LandmarkAdapter,
        recognizer: TemporalGestureRecognizer,
        cancellation: CancellationToken,
    ) -> None:
        super().__init__()
        self._runtime = runtime
        self._landmark_adapter = landmark_adapter
        self._recognizer = recognizer
        self._cancellation = cancellation
        self._session_input = InputAdapter(EventBus(max_size=100))
        self._voice_runner: MicrophonePushToTalk | None = None

    @Slot()
    def run(self) -> None:
        try:
            confirmed = asyncio.run(self._run_session())
        except Exception as exc:  # pragma: no cover - defensive GUI boundary
            self.failed.emit("".join(traceback.format_exception(exc)))
            return
        finally:
            close = getattr(self._landmark_adapter, "close", None)
            if close is not None:
                close()
        self.finished.emit(confirmed)

    async def _run_session(self) -> int:
        capture = GestureCaptureLoop(
            landmark_adapter=self._landmark_adapter,
            recognizer=self._recognizer,
            input_adapter=self._session_input,
        )
        listening_loop = GestureListeningLoop(
            capture=capture,
            cancellation=self._cancellation,
            stop_gesture_id="open_palm",
            on_confirmed=self._on_confirmed,
        )
        try:
            return await listening_loop.run()
        finally:
            # Only the explicit open-palm send gesture submits speech.
            # Cancellation, shutdown, and camera failures discard it.
            voice_runner, self._voice_runner = self._voice_runner, None
            if voice_runner is not None:
                voice_runner.cancel()

    async def _dispatch(self, event: EventBase) -> ActionResult | None:
        """Run one event through the real orchestrator and return its result, if any.

        Used for both a confirmed `GestureEvent` and a sent voice
        `TranscriptEvent`. `process_event()` publishes to the *real* shared
        `runtime.output_bus` (the same bus `_process_runtime_text`'s
        `_drain_runtime_outputs` reads), so this drains it immediately
        rather than only at session end -- otherwise a result could sit in
        the bus and leak into an unrelated later typed command's rendered
        result as a stale `ActionResult`.
        """

        await self._runtime.orchestrator.process_event(event)
        outputs = await _drain_runtime_outputs(self._runtime)
        return next((o for o in outputs if isinstance(o, ActionResult)), None)

    async def _on_confirmed(self, event: GestureEvent) -> None:
        if event.gesture_id == "closed_fist" and self._voice_runner is None:
            await self._start_voice_capture()
        elif event.gesture_id == "open_palm" and self._voice_runner is not None:
            await self._send_voice_capture()

        result = await self._dispatch(event)
        self.gesture_confirmed.emit(event.gesture_id)
        if result is not None:
            self.dispatched.emit(result.message)

    async def _start_voice_capture(self) -> None:
        try:
            from visionai.orchestration.microphone_capture import MicrophonePushToTalk

            self._voice_runner = MicrophonePushToTalk(
                input_adapter=self._session_input,
                capture=_build_microphone_capture(),
                transcribe=_build_transcriber(),
            )
            self._voice_runner.press()
            self.dispatched.emit("Voice command listening started. Show an open palm to send it.")
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            self._voice_runner = None
            self.dispatched.emit(f"Voice input unavailable: {exc}")

    async def _send_voice_capture(self) -> None:
        voice_runner, self._voice_runner = self._voice_runner, None
        if voice_runner is None:
            return
        transcript = await voice_runner.release()
        if transcript is None or not transcript.text.strip():
            self.dispatched.emit("No speech recognized.")
            return
        result = await self._dispatch(transcript)
        if result is not None:
            self.dispatched.emit(result.message)
        else:
            self.dispatched.emit(f'Voice command sent: "{transcript.text.strip()}"')


class _AskWorker(QObject):
    """Send one question to the configured LLM provider, off the GUI thread.

    Mirrors `_RuntimeWorker`'s shape but never touches the orchestrator or
    dispatcher at all -- an LLM reply here is only ever shown, never parsed
    as a command, matching `app.py`'s `--ask`.
    """

    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, *, text: str) -> None:
        super().__init__()
        self._text = text

    @Slot()
    def run(self) -> None:
        try:
            provider = _build_llm_provider()
            reply = provider.respond(LLMQuery(text=self._text))
        except (ImportError, ValueError, ProviderError, ValidationError) as exc:
            self.failed.emit(f"Could not get an answer: {exc}")
            return
        self.finished.emit(reply.text)


class _SuggestWorker(QObject):
    """Propose an LLM-mapped command, or dispatch an already-confirmed one.

    Mirrors `_RuntimeWorker`'s multi-mode-via-constructor shape: `text` (the
    free-text request) drives the propose phase; `phrase` (an
    already-reviewed phrase the user has already seen and confirmed) drives
    the dispatch phase. These are always two separate worker
    instances/threads, never one paused mid-run, the same way
    `_handle_confirmation` starts a fresh `_RuntimeWorker` rather than
    resuming one -- the confirmation dialog itself has to run on the GUI
    thread in between, exactly matching `app.py`'s `--suggest`: a real,
    separate human answer (never anything derived from the LLM's own reply)
    gates the unmodified `runtime.dispatcher.dispatch()` call.
    """

    proposed = Signal(str, str)
    message = Signal(str)
    failed = Signal(str)
    clarification_needed = Signal(str, str)

    def __init__(
        self,
        *,
        runtime: Runtime,
        text: str | None = None,
        phrase: str | None = None,
        allow_clarification: bool = True,
    ) -> None:
        super().__init__()
        self._runtime = runtime
        self._text = text
        self._phrase = phrase
        self._allow_clarification = allow_clarification

    @Slot()
    def run(self) -> None:
        try:
            if self._phrase is not None:
                self._dispatch(self._phrase)
            elif self._text is not None:
                self._propose(self._text)
        except Exception as exc:  # pragma: no cover - defensive GUI boundary
            self.failed.emit("".join(traceback.format_exception(exc)))

    def _propose(self, text: str) -> None:
        try:
            provider = _build_llm_provider()
        except (ImportError, ValueError) as exc:
            self.message.emit(f"Could not get a suggestion: {exc}")
            return
        if isinstance(provider, DeterministicFallbackProvider):
            self.message.emit(provider.respond(LLMQuery(text=text)).text)
            return
        try:
            suggestion = suggest_command_result(provider, text)
        except (ProviderError, ValidationError) as exc:
            self.message.emit(f"Could not get a suggestion: {exc}")
            return
        if suggestion.clarification is not None and self._allow_clarification:
            self.clarification_needed.emit(text, suggestion.clarification)
            return
        phrase = suggestion.phrase
        if phrase is None:
            self.message.emit("No matching command found.")
            return
        _intent, plan = self._runtime.planner.plan(phrase)
        if not plan.steps:
            self.message.emit("No matching command found.")
            return
        self.proposed.emit(phrase, plan.summary)

    def _dispatch(self, phrase: str) -> None:
        _intent, plan = self._runtime.planner.plan(phrase)
        if not plan.steps:
            self.message.emit("No matching command found.")
            return
        result = self._runtime.dispatcher.dispatch(
            plan.steps[0], self._runtime.policy_context_factory()
        )
        self.message.emit(result.message)


def _finish_thread(thread: QThread | None) -> None:
    """Join a completed worker before clearing references or re-enabling its UI."""

    if thread is not None:
        # A worker result signal precedes the return from run(). Releasing
        # its window here can otherwise destroy a QThread that is still running.
        thread.quit()
        thread.wait()


class _TextPromptDialog(QDialog):
    """A single free-text input with OK/Cancel -- reused for Ask AI and Suggest Command."""

    def __init__(self, title: str, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)

        self._input = QLineEdit()
        self._input.setAccessibleName(label)

        form = QFormLayout()
        form.addRow(f"{label}:", self._input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def text(self) -> str:
        return self._input.text()


class _SettingsDialog(QDialog):
    """Editable settings dialog with closed-choice local preferences.

    A combo box restricted to `_LOG_LEVELS` needs no input validation of its
    own -- the widget cannot produce a value outside the valid set.
    """

    def __init__(
        self,
        current: LogLevel,
        microphone_device_index: int | None = None,
        microphone_devices: Sequence[MicrophoneDevice] = (),
        parent: QWidget | None = None,
        wake_word: str = "visionai",
        api_key_configured: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")

        self._log_level_combo = QComboBox()
        self._log_level_combo.setAccessibleName("Log level")
        self._log_level_combo.addItems(_LOG_LEVELS)
        self._log_level_combo.setCurrentIndex(_LOG_LEVELS.index(current))

        self._microphone_combo = QComboBox()
        self._microphone_combo.setAccessibleName("Microphone")
        self._microphone_combo.addItem("Default microphone", None)
        for device in microphone_devices:
            self._microphone_combo.addItem(
                f"{device.name} (device {device.index})", device.index
            )
        selected = self._microphone_combo.findData(microphone_device_index)
        self._microphone_combo.setCurrentIndex(selected if selected >= 0 else 0)

        self._wake_word_input = QLineEdit(wake_word)
        self._wake_word_input.setAccessibleName("Wake word")

        status = "configured" if api_key_configured else "not set"
        self._api_key_status_label = QLabel(f"Anthropic API key: {status}")
        self._api_key_input = QLineEdit()
        self._api_key_input.setAccessibleName("Anthropic API key")
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_input.setPlaceholderText("Leave blank to keep unchanged")
        self._clear_api_key_checkbox = QCheckBox("Clear stored API key")
        self._clear_api_key_checkbox.toggled.connect(self._api_key_input.setDisabled)

        form = QFormLayout()
        form.addRow("Log level:", self._log_level_combo)
        form.addRow("Microphone:", self._microphone_combo)
        form.addRow("Wake word:", self._wake_word_input)
        form.addRow(self._api_key_status_label)
        form.addRow("New API key:", self._api_key_input)
        form.addRow(self._clear_api_key_checkbox)
        key_note = QLabel(
            "Keys are stored in the OS keychain. An environment API key takes priority "
            "and is not removed by clearing the stored key."
        )
        key_note.setWordWrap(True)
        form.addRow(key_note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def selected_log_level(self) -> LogLevel:
        return _LOG_LEVELS[self._log_level_combo.currentIndex()]

    def selected_microphone_device_index(self) -> int | None:
        value = self._microphone_combo.currentData()
        return value if isinstance(value, int) else None

    def selected_wake_word(self) -> str:
        return self._wake_word_input.text()

    def entered_api_key(self) -> str:
        return self._api_key_input.text().strip()

    def clear_api_key_requested(self) -> bool:
        return self._clear_api_key_checkbox.isChecked()


class MainWindow(QMainWindow):
    """Type a command, run it through the real runtime, see the result."""

    def __init__(
        self,
        runtime: Runtime,
        parent: QWidget | None = None,
        *,
        settings_store: UserSettingsStore | None = None,
    ) -> None:
        super().__init__(parent)
        self._runtime = runtime
        self._settings_store = settings_store or default_user_settings_store()
        self._worker_thread: QThread | None = None
        self._worker: _RuntimeWorker | None = None
        self._gesture_thread: QThread | None = None
        self._gesture_worker: _GestureListenWorker | None = None
        self._gesture_cancellation: CancellationToken | None = None
        self._gesture_confirmed_count = 0
        self._ask_thread: QThread | None = None
        self._ask_worker: _AskWorker | None = None
        self._ask_memory = ConversationMemory()
        self._pending_ask_question: str | None = None
        self._suggest_thread: QThread | None = None
        self._suggest_worker: _SuggestWorker | None = None
        self._closing = False
        self.setWindowTitle("VisionAI")

        self._status_label = QLabel(self._runtime.state_machine.state.name)
        self._status_label.setAccessibleName("Current state")

        command_label = QLabel("Command:")
        self._command_input = QLineEdit()
        self._command_input.setAccessibleName("Command input")
        self._command_input.setPlaceholderText('e.g. "open notepad", "what time is it"')
        command_label.setBuddy(self._command_input)
        self._run_button = QPushButton("Run")
        self._run_button.setAccessibleName("Run command")
        self._stop_button = QPushButton("Stop")
        self._stop_button.setAccessibleName("Stop current operation")
        self._stop_button.setToolTip("Request cooperative cancellation of the current operation")
        self._diagnostics_button = QPushButton("Diagnostics")
        self._diagnostics_button.setAccessibleName("Show diagnostics")
        self._settings_button = QPushButton("Settings")
        self._settings_button.setAccessibleName("Show settings")
        self._gesture_button = QPushButton("Start Gesture Control")
        self._gesture_button.setAccessibleName("Toggle gesture control")
        self._gesture_button.setToolTip(
            "Watch the webcam for hand gestures and dispatch their mapped commands "
            "through the same policy and confirmation checks as typed commands"
        )
        self._ask_button = QPushButton("Ask AI")
        self._ask_button.setAccessibleName("Ask AI a question")
        self._ask_button.setToolTip(
            "Ask the configured LLM provider one question -- conversation only, "
            "never dispatches a command"
        )
        self._suggest_button = QPushButton("Suggest Command")
        self._suggest_button.setAccessibleName("Ask AI to suggest a command")
        self._suggest_button.setToolTip(
            "Ask the LLM to propose a command for free text, then ask before "
            "running it through the same policy and dispatcher as a typed command"
        )
        self._clear_conversation_button = QPushButton("Clear Conversation")
        self._clear_conversation_button.setAccessibleName("Clear Ask AI conversation memory")
        self._clear_conversation_button.setToolTip(
            "Delete the Ask AI conversation history remembered for this window session "
            "(never persisted to disk)"
        )

        self._output = QTextEdit()
        self._output.setReadOnly(True)
        self._output.setAccessibleName("Command result")

        self._history = QListWidget()
        self._history.setAccessibleName("Audit history")

        input_row = QHBoxLayout()
        input_row.addWidget(command_label)
        input_row.addWidget(self._command_input)
        input_row.addWidget(self._run_button)
        input_row.addWidget(self._stop_button)
        input_row.addWidget(self._diagnostics_button)
        input_row.addWidget(self._settings_button)
        input_row.addWidget(self._gesture_button)
        input_row.addWidget(self._ask_button)
        input_row.addWidget(self._suggest_button)
        input_row.addWidget(self._clear_conversation_button)

        result_label = QLabel("Result:")
        result_label.setBuddy(self._output)
        history_label = QLabel("History:")
        history_label.setBuddy(self._history)

        layout = QVBoxLayout()
        layout.addWidget(self._status_label)
        layout.addLayout(input_row)
        layout.addWidget(result_label)
        layout.addWidget(self._output)
        layout.addWidget(history_label)
        layout.addWidget(self._history)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        self._run_button.clicked.connect(self.run_current_command)
        self._command_input.returnPressed.connect(self.run_current_command)
        self._stop_button.clicked.connect(self.stop_current_operation)
        self._diagnostics_button.clicked.connect(self.show_diagnostics)
        self._settings_button.clicked.connect(self.show_settings)
        self._gesture_button.clicked.connect(self.toggle_gesture_listening)
        self._ask_button.clicked.connect(self.show_ask_ai)
        self._suggest_button.clicked.connect(self.show_suggest_command)
        self._clear_conversation_button.clicked.connect(self.clear_ask_conversation)
        self._refresh_history()
        self._command_input.setFocus()

        # Placeholder icon: no branded VisionAI icon asset exists yet (Phase 8
        # release work). Using a standard style icon rather than fabricating one.
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self._tray_menu = QMenu()
        self._show_action = self._tray_menu.addAction("Show VisionAI")
        self._show_action.triggered.connect(self._show_and_raise)
        self._quit_action = self._tray_menu.addAction("Quit")
        self._quit_action.triggered.connect(self._quit_application)
        self._tray_icon = QSystemTrayIcon(icon, self)
        self._tray_icon.setToolTip("VisionAI")
        self._tray_icon.setContextMenu(self._tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

    def _show_and_raise(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def _quit_application(self) -> None:
        """Fully exit, bypassing the minimize-to-tray closeEvent behavior."""

        if not self._prepare_close():
            QTimer.singleShot(50, self._quit_application)
            return
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _prepare_close(self) -> bool:
        """Cancel active work and defer destruction until all threads have exited."""

        self._closing = True
        self._pending_ask_question = None
        self._ask_memory.clear()
        if not any((
            self._worker_thread, self._gesture_thread, self._ask_thread, self._suggest_thread
        )):
            return True
        self.setEnabled(False)
        self._runtime.operations.cancel_active_operation()
        if self._gesture_cancellation is not None:
            self._gesture_cancellation.cancel()
        self._output.setPlainText("Stopping active work before closing...")
        return False

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self._show_and_raise()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Minimize to tray instead of quitting, if a tray is actually available.

        Never traps the user: if no system tray exists to un-hide the window
        from (e.g. some minimal window managers, or this headless test
        platform), the window closes normally instead.
        """

        if QSystemTrayIcon.isSystemTrayAvailable():
            event.ignore()
            self.hide()
        elif not self._prepare_close():
            event.ignore()
            QTimer.singleShot(50, self.close)
        else:
            event.accept()

    def show_diagnostics(self) -> None:
        """Show the diagnostics view (Section 6/14's required UI component)."""

        QMessageBox.information(self, "Diagnostics", self._diagnostics_text())

    def show_settings(self) -> None:
        """Show current settings; local log and microphone choices can change here.

        `log_dir`/`data_dir` are
        environment-only (see `visionai.config.settings`) since changing a
        storage path at runtime would need a migration step this dialog
        does not perform.
        """

        current = effective_log_level(self._settings_store)
        current_device = self._settings_store.get_microphone_device_index()
        current_wake_word = effective_wake_word(self._settings_store)
        try:
            from visionai.platform.microphone import list_input_devices

            devices = list_input_devices()
        except Exception:
            devices = []
        try:
            api_key_configured = resolve_anthropic_api_key(get_settings()) is not None
        except (ImportError, StorageError):
            api_key_configured = False
        chosen = self._ask_new_settings(
            current, current_device, devices, current_wake_word, api_key_configured
        )
        if chosen is None:
            return
        chosen_level, chosen_device, chosen_wake_word, api_key_input, clear_api_key = chosen

        if clear_api_key and api_key_input:
            QMessageBox.warning(self, "Settings", "Choose either a new key or clear stored key.")
            return
        if chosen_wake_word != current_wake_word:
            try:
                self._settings_store.set_wake_word(chosen_wake_word)
            except (ValueError, StorageError) as exc:
                QMessageBox.warning(self, "Settings", str(exc))
                return
        if clear_api_key:
            try:
                default_secret_store().delete("anthropic_api_key")
            except (ImportError, StorageError) as exc:
                QMessageBox.warning(self, "Settings", f"Could not remove the key: {exc}")
                return
        elif api_key_input:
            try:
                default_secret_store().set("anthropic_api_key", api_key_input)
            except (ImportError, StorageError) as exc:
                QMessageBox.warning(self, "Settings", f"Could not store the key: {exc}")
                return
        if chosen_level != current:
            self._settings_store.set_log_level(chosen_level)
            configure_logging(chosen_level)
        if chosen_device != current_device:
            self._settings_store.set_microphone_device_index(chosen_device)
        QMessageBox.information(
            self, "Settings", "Settings saved."
        )

    def _ask_new_settings(
        self,
        current: LogLevel,
        current_device: int | None,
        devices: Sequence[MicrophoneDevice],
        current_wake_word: str,
        api_key_configured: bool = False,
    ) -> tuple[LogLevel, int | None, str, str, bool] | None:
        """Show the editable settings dialog, or return None when cancelled."""

        dialog = _SettingsDialog(
            current,
            current_device,
            devices,
            self,
            wake_word=current_wake_word,
            api_key_configured=api_key_configured,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return (
            dialog.selected_log_level(),
            dialog.selected_microphone_device_index(),
            dialog.selected_wake_word(),
            dialog.entered_api_key(),
            dialog.clear_api_key_requested(),
        )

    def _settings_text(self) -> str:
        """Build the settings summary shown before editing."""

        settings = get_settings()
        lines = [
            f"Log level: {effective_log_level(self._settings_store)}",
            f"Log directory: {settings.log_dir}",
            f"Data directory: {settings.data_dir}",
            "Raw audio retention: disabled",
            "Raw camera retention: disabled",
            "Permissions: managed by policy store, not this dialog",
            f"Wake word: {effective_wake_word(self._settings_store)}",
            "Settings editing: log level, microphone selection, and wake word",
        ]
        return "\n".join(lines)

    def maybe_show_onboarding(self) -> None:
        """Show the one-time welcome dialog, if it has not been seen yet.

        Called explicitly by `main()` after the window is shown, not from
        `__init__`: a modal dialog fired during construction would block
        every test that builds a `MainWindow` without expecting one.
        """

        if self._settings_store.has_seen_onboarding():
            return
        QMessageBox.information(self, "Welcome to VisionAI", _ONBOARDING_TEXT)
        self._settings_store.mark_onboarding_seen()

    def _diagnostics_text(self) -> str:
        """Build the diagnostics summary. Read-only introspection only.

        Every value here is either a library/environment fact or read
        straight off the runtime's own registry/state; nothing here can
        affect policy, dispatch, or the state machine.
        """

        tray_status = "available" if QSystemTrayIcon.isSystemTrayAvailable() else "not available"
        lines = [
            f"VisionAI: {visionai.__version__}",
            f"Python: {sys.version.split()[0]}",
            f"PySide6: {PySide6.__version__}",
            f"Registered capabilities: {len(self._runtime.registry.list())}",
            f"System tray: {tray_status}",
            f"State: {self._runtime.state_machine.state.name}",
            "Voice input: available via Gesture Control and CLI wake-word listening",
            "Camera/vision input: available via the Gesture Control button (needs a webcam)",
            "Speech/vision processing: local only (no cloud provider configured)",
            f"LLM provider: {get_settings().llm_provider}",
            f"Ask AI conversation memory: {len(self._ask_memory.turns)} turn(s) "
            "retained this session (never persisted; Clear Conversation deletes it)",
        ]
        return "\n".join(lines)

    def stop_current_operation(self) -> None:
        """Request cooperative cancellation, independent of the Run/input state."""

        if self._is_worker_running():
            if self._runtime.operations.cancel_active_operation():
                self._output.setPlainText("Stop requested.")
            else:
                self._output.setPlainText("No operation is currently running.")
            self._status_label.setText(self._runtime.state_machine.state.name)
            return

        self._command_input.setEnabled(False)
        self._run_button.setEnabled(False)
        self._start_worker(text="stop")

    def run_current_command(self) -> None:
        """Plan and dispatch the text currently in the command input."""

        if self._is_worker_running():
            return

        text = self._command_input.text().strip()
        if not text:
            return

        self._command_input.setEnabled(False)
        self._run_button.setEnabled(False)
        self._start_worker(text=text)

    def toggle_gesture_listening(self) -> None:
        """Start or stop continuous webcam gesture recognition.

        A confirmed gesture reaches the runtime exactly the way a typed
        command does -- the same `TextCommandPlanner`/policy/dispatcher
        path, gated by the same confirmation and permission prompts this
        window already shows -- so gesture recognition carries no extra
        authority. Runs independently of the text-command worker: dispatch
        is already safe under concurrent callers (see `PROJECT_STATE.md`'s
        `StateMachine`/rate-limiter thread-safety fixes), so Run/Stop stay
        usable while gesture control is listening.
        """

        if self._gesture_thread is not None:
            if self._gesture_cancellation is not None:
                self._gesture_cancellation.cancel()
            self._gesture_button.setEnabled(False)
            self._gesture_button.setText("Stopping...")
            return

        try:
            landmark_adapter = _build_landmark_adapter()
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            self._output.setPlainText(f"Gesture control unavailable: {exc}")
            return

        self._gesture_confirmed_count = 0
        self._gesture_cancellation = _build_gesture_cancellation_token()
        thread = QThread(self)
        worker = _GestureListenWorker(
            runtime=self._runtime,
            landmark_adapter=landmark_adapter,
            recognizer=TemporalGestureRecognizer(),
            cancellation=self._gesture_cancellation,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.gesture_confirmed.connect(self._on_gesture_confirmed)
        worker.dispatched.connect(self._on_gesture_dispatched)
        worker.finished.connect(self._on_gesture_finished)
        worker.failed.connect(self._on_gesture_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._gesture_thread = thread
        self._gesture_worker = worker
        thread.start()
        self._gesture_button.setText("Stop Gesture Control (0 confirmed)")

    def _on_gesture_confirmed(self, gesture_id: str) -> None:
        self._gesture_confirmed_count += 1
        self._gesture_button.setText(
            f"Stop Gesture Control ({self._gesture_confirmed_count} confirmed)"
        )
        self._status_label.setText(self._runtime.state_machine.state.name)

    def _on_gesture_dispatched(self, message: str) -> None:
        self._output.setPlainText(message)
        self._refresh_history()
        self._status_label.setText(self._runtime.state_machine.state.name)

    def _on_gesture_finished(self, confirmed: int) -> None:
        _finish_thread(self._gesture_thread)
        self._gesture_thread = None
        self._gesture_worker = None
        self._gesture_cancellation = None
        self._gesture_button.setText("Start Gesture Control")
        self._gesture_button.setEnabled(True)
        self._output.setPlainText(f"Gesture control stopped. {confirmed} gesture(s) confirmed.")
        self._status_label.setText(self._runtime.state_machine.state.name)
        self._refresh_history()

    def _on_gesture_failed(self, message: str) -> None:
        _finish_thread(self._gesture_thread)
        self._gesture_thread = None
        self._gesture_worker = None
        self._gesture_cancellation = None
        self._gesture_button.setText("Start Gesture Control")
        self._gesture_button.setEnabled(True)
        self._output.setPlainText(f"Gesture control error: {message}")

    def _prompt_for_text(self, title: str, label: str) -> str | None:
        """Show a single free-text prompt, or return None if cancelled/empty."""

        dialog = _TextPromptDialog(title, label, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        text = dialog.text().strip()
        return text or None

    def show_ask_ai(self) -> None:
        """Ask the configured LLM one question. Conversation only -- dispatches nothing.

        Prior turns from this window session (if any) are prefixed onto the
        outgoing question by `ConversationMemory.build_query_text()` -- the
        LLM provider boundary itself still only ever sees one `LLMQuery`
        text, never a separate history structure.
        """

        if self._ask_thread is not None:
            return
        text = self._prompt_for_text("Ask AI", "Question")
        if text is None:
            return

        self._pending_ask_question = text
        self._ask_button.setEnabled(False)
        thread = QThread(self)
        worker = _AskWorker(text=self._ask_memory.build_query_text(text))
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_ask_finished)
        worker.failed.connect(self._on_ask_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._ask_thread = thread
        self._ask_worker = worker
        thread.start()

    def _on_ask_finished(self, message: str) -> None:
        _finish_thread(self._ask_thread)
        self._ask_thread = None
        self._ask_worker = None
        self._ask_button.setEnabled(True)
        self._output.setPlainText(message)
        if self._pending_ask_question is not None:
            self._ask_memory.record(self._pending_ask_question, message)
            self._pending_ask_question = None

    def _on_ask_failed(self, message: str) -> None:
        _finish_thread(self._ask_thread)
        self._ask_thread = None
        self._ask_worker = None
        self._pending_ask_question = None
        self._ask_button.setEnabled(True)
        self._output.setPlainText(message)

    def clear_ask_conversation(self) -> None:
        """Delete the Ask AI conversation history remembered for this session."""

        self._ask_memory.clear()
        self._pending_ask_question = None
        self._output.setPlainText("Ask AI conversation memory cleared.")

    def show_suggest_command(self) -> None:
        """Ask the LLM to propose a command, then ask before dispatching it."""

        if self._suggest_thread is not None:
            return
        text = self._prompt_for_text("Suggest Command", "Request")
        if text is None:
            return
        self._start_suggest_worker(text=text)

    def _start_suggest_worker(
        self,
        *,
        text: str | None = None,
        phrase: str | None = None,
        allow_clarification: bool = True,
    ) -> None:
        self._suggest_button.setEnabled(False)
        thread = QThread(self)
        worker = _SuggestWorker(
            runtime=self._runtime,
            text=text,
            phrase=phrase,
            allow_clarification=allow_clarification,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.proposed.connect(self._on_suggest_proposed)
        worker.message.connect(self._on_suggest_message)
        worker.failed.connect(self._on_suggest_failed)
        worker.clarification_needed.connect(self._on_suggest_clarification_needed)
        worker.proposed.connect(thread.quit)
        worker.message.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.clarification_needed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._suggest_thread = thread
        self._suggest_worker = worker
        thread.start()

    def _on_suggest_clarification_needed(self, original_text: str, question: str) -> None:
        _finish_thread(self._suggest_thread)
        self._suggest_thread = None
        self._suggest_worker = None
        if self._closing:
            return
        answer = self._prompt_for_text("Suggest Command", question)
        if not answer:
            self._suggest_button.setEnabled(True)
            self._output.setPlainText("Cancelled.")
            return
        self._start_suggest_worker(
            text=f"{original_text} {answer}", allow_clarification=False
        )

    def _on_suggest_proposed(self, phrase: str, summary: str) -> None:
        _finish_thread(self._suggest_thread)
        self._suggest_thread = None
        self._suggest_worker = None
        if self._closing:
            return
        self._output.setPlainText(f"Proposed: {summary}")
        if self._ask_execute_confirmation(summary):
            self._start_suggest_worker(phrase=phrase)
        else:
            self._suggest_button.setEnabled(True)
            self._output.setPlainText("Cancelled.")

    def _on_suggest_message(self, message: str) -> None:
        _finish_thread(self._suggest_thread)
        self._suggest_thread = None
        self._suggest_worker = None
        self._suggest_button.setEnabled(True)
        self._output.setPlainText(message)
        self._refresh_history()
        self._status_label.setText(self._runtime.state_machine.state.name)

    def _on_suggest_failed(self, message: str) -> None:
        _finish_thread(self._suggest_thread)
        self._suggest_thread = None
        self._suggest_worker = None
        self._suggest_button.setEnabled(True)
        self._output.setPlainText(message)

    def _ask_execute_confirmation(self, summary: str) -> bool:
        answer = QMessageBox.question(
            self,
            "Execute this command?",
            summary,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _start_worker(
        self,
        *,
        text: str | None = None,
        confirmation: ConfirmationRequest | None = None,
        permission: PermissionRequest | None = None,
    ) -> None:
        thread = QThread(self)
        worker = _RuntimeWorker(
            runtime=self._runtime, text=text, confirmation=confirmation, permission=permission
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_worker_finished)
        worker.failed.connect(self._on_worker_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._worker_thread = thread
        self._worker = worker
        thread.start()

    def _is_worker_running(self) -> bool:
        return self._worker_thread is not None

    def _clear_worker(self) -> None:
        _finish_thread(self._worker_thread)
        self._worker_thread = None
        self._worker = None

    def _on_worker_finished(self, outputs: list[EventBase]) -> None:
        self._clear_worker()

        if self._closing:
            for output in outputs:
                if isinstance(output, ConfirmationRequest):
                    self._runtime.orchestrator.cancel_pending_confirmation(output.id)
                elif isinstance(output, PermissionRequest):
                    self._runtime.orchestrator.cancel_pending_permission(output.id)
            return

        confirmation_result = self._handle_confirmation(outputs)
        if confirmation_result is not None:
            outputs = confirmation_result
            if self._is_worker_running():
                return

        permission_result = self._handle_permission(outputs)
        if permission_result is not None:
            outputs = permission_result
            if self._is_worker_running():
                return

        self._render_result(outputs)
        self._status_label.setText(self._runtime.state_machine.state.name)
        self._refresh_history()
        self._command_input.clear()
        self._command_input.setEnabled(True)
        self._run_button.setEnabled(True)
        self._command_input.setFocus()

    def _on_worker_failed(self, message: str) -> None:
        self._clear_worker()
        self._output.setPlainText(f"Error: {message}")
        self._status_label.setText(self._runtime.state_machine.state.name)
        self._command_input.setEnabled(True)
        self._run_button.setEnabled(True)
        self._command_input.setFocus()

    def _handle_confirmation(self, outputs: list[EventBase]) -> list[EventBase] | None:
        confirmation = next((o for o in outputs if isinstance(o, ConfirmationRequest)), None)
        if confirmation is None:
            return None

        if self._ask_confirmation(confirmation):
            self._start_worker(confirmation=confirmation)
            return []

        self._runtime.orchestrator.cancel_pending_confirmation(confirmation.id)
        return [ActionPlan(steps=(), summary="Action cancelled.")]

    def _handle_permission(self, outputs: list[EventBase]) -> list[EventBase] | None:
        permission = next((o for o in outputs if isinstance(o, PermissionRequest)), None)
        if permission is None:
            return None

        if self._ask_permission(permission):
            self._start_worker(permission=permission)
            return []

        self._runtime.orchestrator.cancel_pending_permission(permission.id)
        return [ActionPlan(steps=(), summary="Permission not granted.")]

    def _ask_confirmation(self, confirmation: ConfirmationRequest) -> bool:
        answer = QMessageBox.question(
            self,
            "Confirm action",
            confirmation.action_summary,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _ask_permission(self, permission: PermissionRequest) -> bool:
        answer = QMessageBox.question(
            self,
            "Grant permission",
            f"Allow {permission.capability_id}?\n\n{permission.action_summary}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _render_result(self, outputs: list[EventBase]) -> None:
        result = next((o for o in outputs if isinstance(o, ActionResult)), None)
        error = next((o for o in outputs if isinstance(o, ErrorEvent)), None)
        if result is not None:
            self._output.setPlainText(result.message)
        elif error is not None:
            self._output.setPlainText(f"Error: {error.message}")
        else:
            plan = next((o for o in outputs if isinstance(o, ActionPlan)), None)
            self._output.setPlainText(plan.summary if plan is not None else "No response.")

    def _refresh_history(self) -> None:
        self._history.clear()
        for entry in self._runtime.audit.list():
            self._history.addItem(f"[{entry.category}] {entry.summary}")


def main() -> int:
    """Launch the desktop UI against a freshly built runtime."""

    configure_logging(effective_log_level(default_user_settings_store()))
    app = QApplication(sys.argv)
    window = MainWindow(build_runtime())
    window.show()
    window.maybe_show_onboarding()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
