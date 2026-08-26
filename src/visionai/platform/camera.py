"""Camera/landmark adapter boundary for gesture recognition.

Mirrors `visionai.platform.lock_state`: a small `Protocol` isolates the
trusted runtime from any real camera/landmark library, plus a fixed test
double. A real implementation (webcam frame capture and landmark
classification, e.g. via OpenCV/MediaPipe) belongs behind this interface
and must be covered by its own tests before the recognizer or input
adapter ever depends on it -- this module only defines the boundary and
the single-frame candidate shape handed across it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol


@dataclass(frozen=True, slots=True)
class GestureCandidate:
    """One raw, already-classified single-frame gesture candidate.

    `gesture_id=None` means nothing was recognized in this frame -- the
    same "no gesture this frame" case `TemporalGestureRecognizer.observe()`
    already treats as a reset, not an error.
    """

    gesture_id: str | None
    hand: Literal["left", "right"] = "right"
    confidence: float = 0.0


class LandmarkAdapter(Protocol):
    """Produces one gesture candidate per call.

    No camera or landmark-model detail leaks past this boundary; a real
    adapter owns its own frame capture and per-frame classification
    internally and only ever hands back a `GestureCandidate`.
    """

    def read_candidate(self) -> GestureCandidate:
        """Return the current frame's classification."""


@dataclass(slots=True)
class StaticLandmarkAdapter:
    """Test adapter that replays a fixed sequence of candidates.

    Once exhausted, returns a `None`-gesture candidate on every further
    call rather than raising, matching a real adapter's "nothing detected
    this frame" behavior instead of a special end-of-stream error.
    """

    candidates: list[GestureCandidate] = field(default_factory=list)
    _index: int = field(default=0, init=False)

    def read_candidate(self) -> GestureCandidate:
        if self._index >= len(self.candidates):
            return GestureCandidate(gesture_id=None)
        candidate = self.candidates[self._index]
        self._index += 1
        return candidate
