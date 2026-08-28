"""Real webcam capture and per-frame hand-gesture classification.

Uses OpenCV for camera frame capture and MediaPipe's legacy
`solutions.hands` API for 21-point hand landmark detection, the same
technique the quarantined `../jarvis` prototype used (see
`docs/MIGRATION_QUARANTINE.md`) -- this is a fresh, trusted
reimplementation of the classification heuristic, not a migration of
prototype code. Newer mediapipe releases (0.10.35 and 1.0.1 were both
checked) drop `mediapipe.solutions` from their Windows wheels in favor of
a separate Tasks API that requires downloading a model file at runtime;
pinning to 0.10.14 -- the newest cp312 Windows wheel confirmed to still
ship `solutions.hands` -- keeps hand-landmark detection fully offline with
no model download step. See `requirements/vision.txt`.

`cv2`/`mediapipe` are only imported inside the functions/classes that
touch them, not at module import time, so importing this module -- and
any test that injects its own frame source and classifier -- never
requires the real camera or vision libraries to be present, mirroring
`visionai.platform.microphone`.

Classifies a small fixed vocabulary by counting extended fingers. Anything
ambiguous reports no gesture (`gesture_id=None`) rather than guessing. Only
one classified `GestureCandidate` per frame ever crosses the boundary; raw
frames and landmarks never leave this module.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Literal, Protocol

import numpy as np

from visionai.platform.camera import GestureCandidate

_FINGER_TIPS = (8, 12, 16, 20)
_FINGER_PIPS = (6, 10, 14, 18)
_THUMB_TIP = 4
_THUMB_IP = 3
_OPEN_PALM_MIN_FINGERS = 4


@dataclass(frozen=True, slots=True)
class HandLandmark:
    """One normalized (x, y) landmark point, decoupled from mediapipe's own type."""

    x: float
    y: float


def classify_finger_count(
    landmarks: Sequence[HandLandmark], handedness: Literal["left", "right"]
) -> str | None:
    """Pure heuristic: 21 hand landmarks -> a simple gesture ID or ``None``.

    No camera or model dependency -- fully unit-testable with fixture
    coordinates. Extended-finger detection compares each fingertip to its
    PIP joint (True camera-Y increases downward, so "up" means a smaller
    y); the thumb compares x instead, mirrored by handedness.
    """

    non_thumb_fingers_up = 0
    for tip, pip in zip(_FINGER_TIPS, _FINGER_PIPS, strict=True):
        if landmarks[tip].y < landmarks[pip].y:
            non_thumb_fingers_up += 1
    thumb_tip, thumb_ip = landmarks[_THUMB_TIP], landmarks[_THUMB_IP]
    thumb_up = thumb_tip.x > thumb_ip.x if handedness == "left" else thumb_tip.x < thumb_ip.x

    if non_thumb_fingers_up == 0 and not thumb_up:
        return "closed_fist"
    if non_thumb_fingers_up == 0 and thumb_up:
        return "thumbs_up"
    if non_thumb_fingers_up == 1 and not thumb_up:
        return "index_finger_up"
    if non_thumb_fingers_up == 2 and not thumb_up:
        return "peace_sign"
    if non_thumb_fingers_up == 2 and thumb_up:
        return "two_fingers"
    if non_thumb_fingers_up + int(thumb_up) >= _OPEN_PALM_MIN_FINGERS:
        return "open_palm"
    return None


class FrameSource(Protocol):
    """The minimal real camera surface this module depends on."""

    def read(self) -> np.ndarray | None: ...

    def release(self) -> None: ...


class _CvFrameSource:
    """Real `FrameSource` backed by an OpenCV `VideoCapture`."""

    def __init__(self, device: int) -> None:
        cv2 = import_module("cv2")
        self._cap = cv2.VideoCapture(device, cv2.CAP_DSHOW)

    def read(self) -> np.ndarray | None:
        ok, frame = self._cap.read()
        return frame if ok else None

    def release(self) -> None:
        self._cap.release()


def _default_hands() -> Any:
    mp = import_module("mediapipe")
    return mp.solutions.hands.Hands(
        max_num_hands=1, min_detection_confidence=0.6, min_tracking_confidence=0.5
    )


def classify_hand_frame(frame: np.ndarray, hands: Any) -> GestureCandidate:
    """Run one BGR frame through a mediapipe `Hands` instance and classify it."""

    cv2 = import_module("cv2")
    result = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    if not result.multi_hand_landmarks or not result.multi_handedness:
        return GestureCandidate(gesture_id=None)

    raw_landmarks = result.multi_hand_landmarks[0].landmark
    landmarks = [HandLandmark(x=point.x, y=point.y) for point in raw_landmarks]
    handedness_entry = result.multi_handedness[0].classification[0]
    hand: Literal["left", "right"] = "right" if handedness_entry.label == "Right" else "left"
    confidence = float(handedness_entry.score)

    gesture_id = classify_finger_count(landmarks, hand)
    return GestureCandidate(gesture_id=gesture_id, hand=hand, confidence=confidence)


Classifier = Callable[[np.ndarray], GestureCandidate]


class WebcamLandmarkAdapter:
    """Real `LandmarkAdapter`: one webcam frame -> one classified gesture candidate.

    Frame capture and hand classification are both injectable
    (`frame_source`, `classifier`) so the automated suite never needs a
    real camera or the `vision` extra installed, matching
    `MicrophoneCapture`'s injectable `stream_factory`. `close()` releases
    the real camera device and the mediapipe model once done.
    """

    def __init__(
        self,
        *,
        device: int = 0,
        frame_source: FrameSource | None = None,
        classifier: Classifier | None = None,
    ) -> None:
        self._frame_source: FrameSource = frame_source or _CvFrameSource(device)
        self._owns_hands = classifier is None
        if classifier is not None:
            self._classifier = classifier
        else:
            hands = _default_hands()
            self._hands = hands
            self._classifier = lambda frame: classify_hand_frame(frame, hands)

    def read_candidate(self) -> GestureCandidate:
        frame = self._frame_source.read()
        if frame is None:
            return GestureCandidate(gesture_id=None)
        return self._classifier(frame)

    def close(self) -> None:
        self._frame_source.release()
        if self._owns_hands:
            self._hands.close()
