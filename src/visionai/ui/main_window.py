"""Minimal desktop main window: a thin front end over the safe runtime.

This is the first Phase 2 slice, not the full main window described in
Section 14 of the master prompt (no onboarding or editable settings yet).
It exists to prove the UI can drive the already-tested
orchestrator/state machine/dispatcher path safely, not to be a finished
product. Every typed command is turned into a final TranscriptEvent and
handed to the same `EventOrchestrator` the CLI and automated tests use --
this window adds no new planning or execution logic of its own. The tray
icon (show/hide, quit), diagnostics view, and read-only settings view are
the exceptions: they are pure window-lifecycle/read-only-introspection
controls with no runtime authority.
"""

from __future__ import annotations

import asyncio
import sys
from typing import TYPE_CHECKING

import PySide6
from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
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
from visionai.config import get_settings
from visionai.core.events import (
    ActionPlan,
    ActionResult,
    ConfirmationRequest,
    ErrorEvent,
    EventBase,
    TranscriptEvent,
)
from visionai.runtime import Runtime, build_runtime

if TYPE_CHECKING:
    from PySide6.QtGui import QCloseEvent


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
    ) -> None:
        super().__init__()
        self._runtime = runtime
        self._text = text
        self._confirmation = confirmation

    @Slot()
    def run(self) -> None:
        try:
            if self._confirmation is not None:
                outputs = asyncio.run(_confirm_runtime_request(self._runtime, self._confirmation))
            elif self._text is not None:
                outputs = asyncio.run(_process_runtime_text(self._runtime, self._text))
            else:
                outputs = []
        except Exception as exc:  # pragma: no cover - defensive GUI boundary
            self.failed.emit(str(exc))
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


async def _drain_runtime_outputs(runtime: Runtime) -> list[EventBase]:
    outputs: list[EventBase] = []
    while runtime.output_bus.size:
        outputs.append(await runtime.output_bus.next_event())
    return outputs


class MainWindow(QMainWindow):
    """Type a command, run it through the real runtime, see the result."""

    def __init__(self, runtime: Runtime, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._runtime = runtime
        self._worker_thread: QThread | None = None
        self._worker: _RuntimeWorker | None = None
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

        app = QApplication.instance()
        if app is not None:
            app.quit()

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
        else:
            event.accept()

    def show_diagnostics(self) -> None:
        """Show the diagnostics view (Section 6/14's required UI component)."""

        QMessageBox.information(self, "Diagnostics", self._diagnostics_text())

    def show_settings(self) -> None:
        """Show current settings without changing them."""

        QMessageBox.information(self, "Settings", self._settings_text())

    def _settings_text(self) -> str:
        """Build the read-only settings summary."""

        settings = get_settings()
        lines = [
            f"Log level: {settings.log_level}",
            f"Log directory: {settings.log_dir}",
            f"Data directory: {settings.data_dir}",
            "Raw audio retention: disabled",
            "Raw camera retention: disabled",
            "Permissions: managed by policy store, not this dialog",
            "Settings editing: not enabled yet",
        ]
        return "\n".join(lines)

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
            "Voice input: not connected (Phase 3 not started)",
            "Camera/vision input: not connected (Phase 5 not started)",
            "Speech/vision processing: local only (no cloud provider configured)",
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

    def _start_worker(
        self,
        *,
        text: str | None = None,
        confirmation: ConfirmationRequest | None = None,
    ) -> None:
        thread = QThread(self)
        worker = _RuntimeWorker(runtime=self._runtime, text=text, confirmation=confirmation)
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
        return self._worker_thread is not None and self._worker_thread.isRunning()

    def _clear_worker(self) -> None:
        self._worker_thread = None
        self._worker = None

    def _on_worker_finished(self, outputs: list[EventBase]) -> None:
        self._clear_worker()

        confirmation_result = self._handle_confirmation(outputs)
        if confirmation_result is not None:
            outputs = confirmation_result
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

    def _ask_confirmation(self, confirmation: ConfirmationRequest) -> bool:
        answer = QMessageBox.question(
            self,
            "Confirm action",
            confirmation.action_summary,
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

    app = QApplication(sys.argv)
    window = MainWindow(build_runtime())
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
