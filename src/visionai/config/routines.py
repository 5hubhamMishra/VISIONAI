"""Persistent named routines: an ordered list of already-reviewed command phrases.

Mirrors `UserSettingsStore`'s atomic-write JSON pattern. This store only
persists names and phrase lists -- it has no opinion on which phrases are
safe to save or run. That judgment (every phrase must already be one
`orchestration.text_planner.reviewed_phrases()` accepts, and must plan to a
Risk 0 (read-only) or Risk 1 (reversible) capability only -- never one that
would itself need a permission grant or confirmation) is enforced by the
caller, `app.py`'s `--routine-save`/`--routine-run`, which has the real
planner and dispatcher this store deliberately does not depend on. A routine
carries no authority of its own: running one is nothing more than replaying
already-individually-approved phrases through the unmodified
`TextCommandPlanner`/policy/dispatcher path, one at a time.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from tempfile import NamedTemporaryFile

from visionai.config.settings import get_settings
from visionai.core.errors import StorageError
from visionai.core.events import contains_unsafe_characters


def normalize_routine_name(name: str) -> str | None:
    """Collapse whitespace and lowercase; return None if empty or unsafe."""

    if contains_unsafe_characters(name, allow_line_breaks=False):
        return None
    normalized = " ".join(name.split()).lower()
    return normalized or None


class RoutineStore:
    """Stores named routines (ordered command-phrase lists) in a small JSON file."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def list_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._read()))

    def get(self, name: str) -> tuple[str, ...] | None:
        normalized = normalize_routine_name(name)
        if normalized is None:
            return None
        value = self._read().get(normalized)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            return None
        return tuple(value)

    def save(self, name: str, phrases: Sequence[str]) -> None:
        normalized = normalize_routine_name(name)
        if normalized is None:
            raise ValueError("routine name must be non-empty and contain no control characters")
        if not phrases:
            raise ValueError("a routine must contain at least one phrase")
        data = self._read()
        data[normalized] = list(phrases)
        self._write(data)

    def delete(self, name: str) -> None:
        normalized = normalize_routine_name(name)
        if normalized is None:
            return
        data = self._read()
        if normalized in data:
            del data[normalized]
            self._write(data)

    def _read(self) -> dict[str, object]:
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StorageError("routine store could not be read") from exc
        if not isinstance(raw, dict):
            raise StorageError("routine store root must be an object")
        return raw

    def _write(self, data: dict[str, object]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with NamedTemporaryFile(
                "w", encoding="utf-8", dir=self._path.parent, delete=False
            ) as temp:
                json.dump(data, temp, indent=2, sort_keys=True)
                temp.write("\n")
                temp_path = Path(temp.name)
            temp_path.replace(self._path)
        except OSError as exc:
            raise StorageError("routine store could not be written") from exc


def default_routine_store() -> RoutineStore:
    """Build the default store, colocated with settings/permissions."""

    return RoutineStore(get_settings().data_dir / "routines.json")
