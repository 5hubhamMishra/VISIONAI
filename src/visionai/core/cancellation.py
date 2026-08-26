"""Cooperative cancellation primitive.

Long-running operations (listening, transcription, LLM calls, capability
execution) should poll `is_cancelled` or block on `wait` instead of being
torn down by killing threads outright, so resources are released cleanly.
"""

import threading


class CancellationToken:
    """A one-shot, thread-safe cancellation signal."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        """Signal cancellation. Idempotent."""
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def wait(self, timeout: float | None = None) -> bool:
        """Block until cancelled or `timeout` elapses.

        Returns True if cancellation was signalled, False on timeout.
        """
        return self._event.wait(timeout)

    def raise_if_cancelled(self) -> None:
        """Raise `OperationCancelled` if cancellation has been signalled."""
        if self.is_cancelled:
            raise OperationCancelled


class OperationCancelled(Exception):
    """Raised by cooperative code paths that check a CancellationToken."""


class OperationController:
    """Tracks at most one cancellable operation for the early runtime."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active_token: CancellationToken | None = None

    def begin_operation(self) -> CancellationToken:
        """Start tracking a new active operation and return its token."""

        token = CancellationToken()
        with self._lock:
            self._active_token = token
        return token

    def finish_operation(self, token: CancellationToken) -> None:
        """Clear the active operation only if `token` is still current."""

        with self._lock:
            if self._active_token is token:
                self._active_token = None

    @property
    def has_active_operation(self) -> bool:
        with self._lock:
            return self._active_token is not None

    def cancel_active_operation(self) -> bool:
        """Cancel the active operation if one exists.

        Returns True when a token was cancelled, False when there was
        nothing active to stop.
        """

        with self._lock:
            token = self._active_token
        if token is None:
            return False
        token.cancel()
        return True
