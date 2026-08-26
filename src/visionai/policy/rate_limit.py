"""Fixed-window capability rate limiting."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from time import monotonic


@dataclass(slots=True)
class _Window:
    started_at: float
    count: int = 0


class FixedWindowRateLimiter:
    """Tracks per-capability calls inside a one-minute window.

    Guarded by a lock: the dispatcher only serializes handler execution,
    not policy evaluation, so this state can be read and mutated from
    multiple recognition threads (voice, gesture, ...) submitting requests
    concurrently.
    """

    def __init__(self, *, clock: Callable[[], float] = monotonic) -> None:
        self._clock = clock
        self._windows: dict[str, _Window] = {}
        self._lock = Lock()

    def allow(self, key: str, limit_per_minute: int) -> bool:
        if limit_per_minute <= 0:
            return False
        now = self._clock()
        with self._lock:
            window = self._windows.get(key)
            if window is None or now - window.started_at >= 60:
                self._windows[key] = _Window(started_at=now, count=1)
                return True
            if window.count >= limit_per_minute:
                return False
            window.count += 1
            return True

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._windows.clear()
                return
            self._windows.pop(key, None)
