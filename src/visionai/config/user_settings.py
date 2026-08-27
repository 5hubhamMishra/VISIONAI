"""Persistent user-editable settings overrides.

Mirrors `visionai.policy.permissions.JsonPermissionStore`'s atomic-write
JSON pattern. Deliberately covers only the fields safe to change at
runtime without restart/migration risk (log level, onboarding-seen,
microphone-device selection, wake word);
`log_dir`/`data_dir` remain environment-only in `Settings`.
"""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import cast, get_args

from visionai.config.settings import LogLevel, get_settings
from visionai.core.errors import StorageError

_VALID_LOG_LEVELS = frozenset(get_args(LogLevel))

DEFAULT_WAKE_WORD = "visionai"
_CONTROL_CHARS = frozenset(chr(c) for c in (*range(0x00, 0x20), 0x7F))


def _normalize_wake_word(word: str) -> str | None:
    """Collapse whitespace and lowercase; return None if empty or unsafe."""

    if any(char in _CONTROL_CHARS for char in word):
        return None
    normalized = " ".join(word.split()).lower()
    return normalized or None


class UserSettingsStore:
    """Stores user-editable settings overrides in a small JSON file."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def get_log_level(self) -> LogLevel | None:
        value = self._read().get("log_level")
        if value not in _VALID_LOG_LEVELS:
            return None
        return cast(LogLevel, value)

    def set_log_level(self, level: LogLevel) -> None:
        data = self._read()
        data["log_level"] = level
        self._write(data)

    def has_seen_onboarding(self) -> bool:
        return self._read().get("onboarding_seen") is True

    def mark_onboarding_seen(self) -> None:
        data = self._read()
        data["onboarding_seen"] = True
        self._write(data)

    def get_wake_word(self) -> str | None:
        value = self._read().get("wake_word")
        if not isinstance(value, str):
            return None
        return _normalize_wake_word(value)

    def set_wake_word(self, word: str) -> None:
        normalized = _normalize_wake_word(word)
        if normalized is None:
            raise ValueError("wake word must be non-empty and contain no control characters")
        data = self._read()
        data["wake_word"] = normalized
        self._write(data)

    def get_microphone_device_index(self) -> int | None:
        value = self._read().get("microphone_device_index")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None
        return value

    def set_microphone_device_index(self, index: int | None) -> None:
        if index is not None and (isinstance(index, bool) or index < 0):
            raise ValueError("microphone device index must be non-negative or None")
        data = self._read()
        data["microphone_device_index"] = index
        self._write(data)

    def _read(self) -> dict[str, object]:
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StorageError("settings store could not be read") from exc
        if not isinstance(raw, dict):
            raise StorageError("settings store root must be an object")
        return raw

    def _write(self, data: dict[str, object]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self._path.parent,
                delete=False,
            ) as temp:
                json.dump(data, temp, indent=2, sort_keys=True)
                temp.write("\n")
                temp_path = Path(temp.name)
            temp_path.replace(self._path)
        except OSError as exc:
            raise StorageError("settings store could not be written") from exc


def effective_log_level(store: UserSettingsStore) -> LogLevel:
    """Return the override log level if set, else the environment default."""

    return store.get_log_level() or get_settings().log_level


def effective_wake_word(store: UserSettingsStore) -> str:
    """Return the override wake word if set, else the built-in default."""

    return store.get_wake_word() or DEFAULT_WAKE_WORD


def default_user_settings_store() -> UserSettingsStore:
    """Build the default store, colocated with the permission store."""

    return UserSettingsStore(get_settings().data_dir / "settings.json")
