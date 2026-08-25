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
