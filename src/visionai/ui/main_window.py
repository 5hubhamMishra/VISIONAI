"""Minimal desktop main window: a thin front end over the safe runtime.

This is the first Phase 2 slice, not the full main window described in
Section 14 of the master prompt (no tray, settings, onboarding, or
diagnostics yet). It exists to prove the UI can drive the already-tested
orchestrator/state machine/dispatcher path safely, not to be a finished
product. Every typed command is turned into a final TranscriptEvent and
handed to the same `EventOrchestrator` the CLI and automated tests use --
this window adds no new planning or execution logic of its own.
"""

from __future__ import annotations

import asyncio
import sys

from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from visionai.core.events import ActionPlan, ActionResult, ErrorEvent, EventBase, TranscriptEvent
from visionai.runtime import Runtime, build_runtime


class MainWindow(QMainWindow):
    """Type a command, run it through the real runtime, see the result."""

    def __init__(self, runtime: Runtime, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._runtime = runtime
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

        layout = QVBoxLayout()
        layout.addWidget(self._status_label)
        layout.addLayout(input_row)
        layout.addWidget(QLabel("Result:"))
        layout.addWidget(self._output)
        layout.addWidget(QLabel("History:"))
        layout.addWidget(self._history)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        self._run_button.clicked.connect(self.run_current_command)
        self._command_input.returnPressed.connect(self.run_current_command)
        self._stop_button.clicked.connect(self.stop_current_operation)
        self._refresh_history()

    def stop_current_operation(self) -> None:
        """Request cooperative cancellation, independent of the Run/input state."""

        outputs = asyncio.run(self._process("stop"))
        self._render_result(outputs)
        self._status_label.setText(self._runtime.state_machine.state.name)
        self._refresh_history()

    def run_current_command(self) -> None:
        """Plan and dispatch the text currently in the command input."""

        text = self._command_input.text().strip()
        if not text:
            return

        self._command_input.setEnabled(False)
        self._run_button.setEnabled(False)
        try:
            outputs = asyncio.run(self._process(text))
        finally:
            self._command_input.setEnabled(True)
            self._run_button.setEnabled(True)

        self._render_result(outputs)
        self._status_label.setText(self._runtime.state_machine.state.name)
        self._refresh_history()
        self._command_input.clear()
        self._command_input.setFocus()

    async def _process(self, text: str) -> list[EventBase]:
        event = TranscriptEvent(text=text, confidence=1.0, language="en", is_final=True)
        await self._runtime.orchestrator.process_event(event)
        outputs: list[EventBase] = []
        while self._runtime.output_bus.size:
            outputs.append(await self._runtime.output_bus.next_event())
        return outputs

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
