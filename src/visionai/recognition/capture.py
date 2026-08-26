"""Ties a camera/landmark adapter to temporal voting and the input bus."""

from __future__ import annotations

from typing import TYPE_CHECKING

from visionai.core.events import GestureEvent
from visionai.platform.camera import LandmarkAdapter
from visionai.recognition.gesture import TemporalGestureRecognizer

if TYPE_CHECKING:
    # Deferred to break the import cycle: event_orchestrator imports
    # visionai.recognition (for TemporalGestureRecognizer), and this module
    # is imported eagerly from visionai.recognition.__init__.
    from visionai.orchestration.event_orchestrator import InputAdapter


class GestureCaptureLoop:
    """Reads one candidate from a `LandmarkAdapter`, votes it, and publishes.

    Deliberately thin: all recognition-safety logic (hold duration,
    rejection, cooldown) lives in `TemporalGestureRecognizer`, and all
    validation/publishing lives in `InputAdapter`. This class only wires
    one frame read to one vote attempt, so a caller (a real camera loop,
    or a test driving it frame by frame) controls the pacing.
    """

    def __init__(
        self,
        *,
        landmark_adapter: LandmarkAdapter,
        recognizer: TemporalGestureRecognizer,
        input_adapter: InputAdapter,
    ) -> None:
        self._landmark_adapter = landmark_adapter
        self._recognizer = recognizer
        self._input_adapter = input_adapter

    async def capture_once(self) -> GestureEvent | None:
        """Read one frame's candidate and publish only if temporal voting confirms it."""

        candidate = self._landmark_adapter.read_candidate()
        return await self._input_adapter.publish_gesture_observation(
            self._recognizer,
            candidate.gesture_id,
            hand=candidate.hand,
            confidence=candidate.confidence,
        )
