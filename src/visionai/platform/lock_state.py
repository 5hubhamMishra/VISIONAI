"""Lock-state adapter boundary.

The default implementation is intentionally conservative and injectable.
Real Windows API integration should live behind this interface and be covered
by platform-specific tests before it is used by policy.
"""

from __future__ import annotations

import ctypes
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import dataclass
from typing import Protocol

from visionai.core.errors import PlatformStateError

_DESKTOP_SWITCHDESKTOP = 0x0100


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
    """Checks whether the interactive Windows desktop is locked.

    Locking the workstation switches the visible desktop to a secure
    desktop that ordinary processes cannot open with OpenInputDesktop; the
    same is true while a UAC consent prompt or other secure desktop is
    shown, which is also a reasonable time to block mutating actions. Any
    failure to check is treated as locked by default. The exception is
    retained in `last_error` for diagnostics without allowing unknown
    state to authorize a mutating action.
    """

    def __init__(
        self,
        *,
        can_open_input_desktop: Callable[[], bool] | None = None,
    ) -> None:
        self._can_open_input_desktop = can_open_input_desktop or _can_open_input_desktop
        self.last_error: PlatformStateError | None = None

    def is_locked(self) -> bool:
        try:
            unlocked = self._can_open_input_desktop()
        except Exception as exc:
            self.last_error = PlatformStateError("Windows lock state could not be checked")
            self.last_error.__cause__ = exc
            return True
        self.last_error = None
        return not unlocked


def _can_open_input_desktop() -> bool:
    """Return True if the input desktop can be opened (workstation unlocked)."""
    user32 = ctypes.windll.user32
    user32.OpenInputDesktop.restype = wintypes.HANDLE
    user32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    user32.CloseDesktop.restype = wintypes.BOOL
    user32.CloseDesktop.argtypes = [wintypes.HANDLE]

    desktop = user32.OpenInputDesktop(0, False, _DESKTOP_SWITCHDESKTOP)
    if not desktop:
        return False
    user32.CloseDesktop(desktop)
    return True
