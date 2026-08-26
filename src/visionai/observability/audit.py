"""Audit event sinks."""

from __future__ import annotations

import json
from pathlib import Path
from threading import Lock

from visionai.core.errors import StorageError
from visionai.core.events import AuditEvent


class InMemoryAuditSink:
    """Stores audit events for tests and early UI integration."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._lock = Lock()

    def record(self, event: AuditEvent) -> None:
        with self._lock:
            self._events.append(event)

    def list(self) -> tuple[AuditEvent, ...]:
        with self._lock:
            return tuple(self._events)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


class JsonlAuditSink:
    """Appends audit events to durable JSON Lines storage."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = Lock()

    def record(self, event: AuditEvent) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        line = event.model_dump_json()
        try:
            with self._lock, self._path.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.write("\n")
        except OSError as exc:
            raise StorageError("audit log could not be written") from exc

    def list(self) -> tuple[AuditEvent, ...]:
        if not self._path.exists():
            return ()
        events: list[AuditEvent] = []
        try:
            with self._lock, self._path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        events.append(AuditEvent.model_validate(json.loads(line)))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise StorageError("audit log could not be read") from exc
        return tuple(events)

    def clear(self) -> None:
        with self._lock:
            try:
                self._path.unlink(missing_ok=True)
            except OSError as exc:
                raise StorageError("audit log could not be cleared") from exc
