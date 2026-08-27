"""Tests for the real webcam/hand-landmark boundary.

`classify_finger_count` is pure landmark-coordinate logic and is tested
directly with fixture points -- no camera or mediapipe needed.
`WebcamLandmarkAdapter` is tested with an injected `FrameSource` and
classifier, the same injection pattern `MicrophoneCapture` uses for
`stream_factory`. `classify_hand_frame` gets one real-backend smoke test
against the actual mediapipe `Hands` model, mirroring
`list_input_devices()`'s real-PortAudio smoke test: it cannot assert a
specific gesture from a synthetic frame, only that the real model runs
cleanly and returns a well-formed `GestureCandidate`.
"""

from __future__ import annotations

import numpy as np

from visionai.platform.camera import GestureCandidate
from visionai.platform.webcam import (
    HandLandmark,
    WebcamLandmarkAdapter,
    classify_finger_count,
    classify_hand_frame,
)

# Landmark indices used by classify_finger_count: tip/PIP pairs for
# index, middle, ring, pinky, then the thumb's tip/IP pair.
_INDEX_TIP, _INDEX_PIP = 8, 6
_MIDDLE_TIP, _MIDDLE_PIP = 12, 10
_RING_TIP, _RING_PIP = 16, 14
_PINKY_TIP, _PINKY_PIP = 20, 18
_THUMB_TIP, _THUMB_IP = 4, 3


def _landmarks(
    *,
    index_up: bool = False,
    middle_up: bool = False,
    ring_up: bool = False,
    pinky_up: bool = False,
    thumb_up: bool = False,
    handedness: str = "right",
) -> list[HandLandmark]:
    points = [HandLandmark(x=0.5, y=0.5) for _ in range(21)]
    for tip, pip, up in (
        (_INDEX_TIP, _INDEX_PIP, index_up),
        (_MIDDLE_TIP, _MIDDLE_PIP, middle_up),
        (_RING_TIP, _RING_PIP, ring_up),
        (_PINKY_TIP, _PINKY_PIP, pinky_up),
    ):
        points[tip] = HandLandmark(x=0.5, y=0.4 if up else 0.6)
        points[pip] = HandLandmark(x=0.5, y=0.5)
    thumb_tip_x = (0.4 if handedness == "right" else 0.6) if thumb_up else 0.5
    points[_THUMB_TIP] = HandLandmark(x=thumb_tip_x, y=0.5)
    points[_THUMB_IP] = HandLandmark(x=0.5, y=0.5)
    return points


def test_all_fingers_curled_is_closed_fist() -> None:
    landmarks = _landmarks()

    assert classify_finger_count(landmarks, "right") == "closed_fist"


def test_all_fingers_extended_is_open_palm() -> None:
    landmarks = _landmarks(
        index_up=True, middle_up=True, ring_up=True, pinky_up=True, thumb_up=True
    )

    assert classify_finger_count(landmarks, "right") == "open_palm"


def test_two_fingers_up_is_not_classified() -> None:
    landmarks = _landmarks(index_up=True, middle_up=True)

    assert classify_finger_count(landmarks, "right") is None


def test_thumb_direction_is_mirrored_by_handedness() -> None:
    # Three non-thumb fingers up, so the thumb alone decides whether this
    # reaches open_palm's four-finger threshold.
    right_hand = _landmarks(index_up=True, middle_up=True, ring_up=True, thumb_up=True)
    left_hand = _landmarks(
        index_up=True, middle_up=True, ring_up=True, thumb_up=True, handedness="left"
    )

    assert classify_finger_count(right_hand, "right") == "open_palm"
    assert classify_finger_count(left_hand, "left") == "open_palm"
    # A right-hand thumb position read with the wrong handedness fails to
    # extend, leaving only three fingers up and no classified gesture.
    assert classify_finger_count(right_hand, "left") is None


class _FakeFrameSource:
    def __init__(self, frames: list[np.ndarray | None]) -> None:
        self._frames = frames
        self.released = False

    def read(self) -> np.ndarray | None:
        return self._frames.pop(0)

    def release(self) -> None:
        self.released = True


def test_adapter_returns_classifier_result_for_a_real_frame() -> None:
    frame = np.zeros((4, 4, 3), dtype=np.uint8)
    source = _FakeFrameSource([frame])
    expected = GestureCandidate(gesture_id="open_palm", hand="right", confidence=0.9)
    adapter = WebcamLandmarkAdapter(frame_source=source, classifier=lambda f: expected)

    candidate = adapter.read_candidate()

    assert candidate == expected


def test_adapter_reports_no_gesture_when_frame_read_fails() -> None:
    source = _FakeFrameSource([None])
    called = False

    def classifier(frame: np.ndarray) -> GestureCandidate:
        nonlocal called
        called = True
        return GestureCandidate(gesture_id="open_palm")

    adapter = WebcamLandmarkAdapter(frame_source=source, classifier=classifier)

    candidate = adapter.read_candidate()

    assert candidate == GestureCandidate(gesture_id=None)
    assert called is False


def test_adapter_close_releases_the_frame_source_without_a_real_model() -> None:
    source = _FakeFrameSource([])
    adapter = WebcamLandmarkAdapter(
        frame_source=source, classifier=lambda f: GestureCandidate(gesture_id=None)
    )

    adapter.close()

    assert source.released is True


def test_classify_hand_frame_runs_against_the_real_mediapipe_model() -> None:
    """Smoke test against the real mediapipe Hands model.

    A blank synthetic frame has no hand to detect -- this only proves the
    real model loads and runs cleanly and returns a well-formed
    GestureCandidate, not a specific classification.
    """

    mediapipe = __import__("mediapipe")
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    hands = mediapipe.solutions.hands.Hands(max_num_hands=1)
    try:
        candidate = classify_hand_frame(frame, hands)
    finally:
        hands.close()

    assert isinstance(candidate, GestureCandidate)
    assert candidate.gesture_id is None
