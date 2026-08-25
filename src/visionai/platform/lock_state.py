"""Lock-state adapter boundary.

The default implementation is intentionally conservative and injectable.
Real Windows API integration should live behind this interface and be covered
by platform-specific tests before it is used by policy.
"""

from __future__ import annotations

import ctypes
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from visionai.core.errors import PlatformStateError


class LockStateAdapter(Protocol):
    """Reports whether mutating actions should be blocked."""

    def is_locked(self) -> bool:
        """Return True when the workstation is locked or state is unknown."""


@dataclass(frozen=True, slots=True)
class StaticLockStateAdapter:
    """Test adapter that returns a fixed lock-state value."""

    locked: bool = True

    def is_locked(self) -> bool:
        return self.locked


class WindowsLockStateAdapter:
    """Checks Windows lock state using read-only session information.

    Any failure is treated as locked by default. The exception is retained in
    `last_error` for diagnostics without allowing unknown state to authorize a
    mutating action.
    """

    def __init__(
        self,
        *,
        process_id_provider: Callable[[], int] | None = None,
        session_id_provider: Callable[[int], int | None] | None = None,
    ) -> None:
        self._process_id_provider = (
            process_id_provider or ctypes.windll.kernel32.GetCurrentProcessId
        )
        self._session_id_provider = session_id_provider or _session_id_for_process
        self.last_error: PlatformStateError | None = None

    def is_locked(self) -> bool:
        try:
            current_process_id = self._process_id_provider()
            session_id = self._session_id_provider(current_process_id)
        except Exception as exc:
            self.last_error = PlatformStateError("Windows lock state could not be checked")
            self.last_error.__cause__ = exc
            return True
        if session_id is None:
            self.last_error = PlatformStateError("Windows session ID is unavailable")
            return True
        self.last_error = None
        return False


def _session_id_for_process(process_id: int) -> int | None:
    session_id = ctypes.c_ulong()
    ok = ctypes.windll.kernel32.ProcessIdToSessionId(process_id, ctypes.byref(session_id))
    if not ok:
        return None
    return int(session_id.value)
