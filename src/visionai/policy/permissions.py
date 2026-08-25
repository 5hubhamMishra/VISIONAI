"""Persistent capability permission storage."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from visionai.core.errors import StorageError


@dataclass(frozen=True, slots=True)
class PermissionGrant:
    """A stored user grant for one capability."""

    capability_id: str
    granted: bool


class JsonPermissionStore:
    """Stores capability grants in a small JSON file with atomic replacement."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def grant(self, capability_id: str) -> None:
        grants = self._read()
        grants[capability_id] = True
        self._write(grants)

    def revoke(self, capability_id: str) -> None:
        grants = self._read()
        grants[capability_id] = False
        self._write(grants)

    def is_granted(self, capability_id: str) -> bool:
        return self._read().get(capability_id, False)

    def granted_capabilities(self) -> frozenset[str]:
        return frozenset(
            capability_id for capability_id, granted in self._read().items() if granted
        )

    def _read(self) -> dict[str, bool]:
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StorageError("permission store could not be read") from exc
        if not isinstance(raw, dict):
            raise StorageError("permission store root must be an object")
        grants: dict[str, bool] = {}
        for key, value in raw.items():
            if not isinstance(key, str) or not isinstance(value, bool):
                raise StorageError("permission store contains invalid entries")
            grants[key] = value
        return grants

    def _write(self, grants: dict[str, bool]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self._path.parent,
                delete=False,
            ) as temp:
                json.dump(grants, temp, indent=2, sort_keys=True)
                temp.write("\n")
                temp_path = Path(temp.name)
            temp_path.replace(self._path)
        except OSError as exc:
            raise StorageError("permission store could not be written") from exc
