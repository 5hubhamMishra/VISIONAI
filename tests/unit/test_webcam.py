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

import types

import numpy as np
import pytest

from visionai.platform import webcam as webcam_module
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

    assert classify_finger_count(landmarks, "right") == "peace_sign"


def test_simple_command_gestures_are_classified() -> None:
    assert classify_finger_count(_landmarks(thumb_up=True), "right") == "thumbs_up"
    assert classify_finger_count(_landmarks(index_up=True), "right") == "index_finger_up"
    assert (
        classify_finger_count(_landmarks(index_up=True, middle_up=True, thumb_up=True), "right")
        == "two_fingers"
    )


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

    Skipped when the optional `vision` extra is not installed: unlike
    `voice`/`intelligence`, `vision.txt` is deliberately not part of
    `requirements/dev.txt` (see docs/DECISIONS/0003-accepted-protobuf-cve.md,
    which keeps mediapipe's transitive protobuf CVE out of the standard
    audited/tested surface), so the standard suite -- including CI -- never
    has mediapipe installed. This still runs for real wherever the `vision`
    extra is installed, matching `list_input_devices()`'s real-backend
    smoke test pattern.
    """

    mediapipe = pytest.importorskip("mediapipe")
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    hands = mediapipe.solutions.hands.Hands(max_num_hands=1)
    try:
        candidate = classify_hand_frame(frame, hands)
    finally:
        hands.close()

    assert isinstance(candidate, GestureCandidate)
    assert candidate.gesture_id is None


class _FakeVideoCapture:
    def __init__(self, device: int, backend: int) -> None:
        self.device = device
        self.backend = backend
        self.released = False
        self._frames: list[tuple[bool, np.ndarray | None]] = [
            (True, np.zeros((2, 2, 3), dtype=np.uint8))
        ]

    def read(self) -> tuple[bool, np.ndarray | None]:
        return self._frames.pop(0) if self._frames else (False, None)

    def release(self) -> None:
        self.released = True


def test_cv_frame_source_delegates_construction_read_and_release_to_opencv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_CvFrameSource` never touches a real camera here: `cv2` itself is a
    fake injected via the module's own `import_module` symbol, the same
    pattern `test_stt.py`/`test_microphone.py` use for their default
    factories -- no real hardware or the optional `vision` extra involved.
    """

    captured: dict[str, object] = {}

    class _FakeCv2:
        CAP_DSHOW = 700

        @staticmethod
        def VideoCapture(device: int, backend: int) -> _FakeVideoCapture:
            captured["device"] = device
            captured["backend"] = backend
            return _FakeVideoCapture(device, backend)

    monkeypatch.setattr(webcam_module, "import_module", lambda name: _FakeCv2())

    source = webcam_module._CvFrameSource(2)

    assert captured == {"device": 2, "backend": _FakeCv2.CAP_DSHOW}
    assert source.read() is not None
    assert source.read() is None
    source.release()
    assert source._cap.released is True


def test_default_hands_builds_the_real_mediapipe_hands_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class _FakeHands:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    fake_mediapipe = types.SimpleNamespace(
        solutions=types.SimpleNamespace(hands=types.SimpleNamespace(Hands=_FakeHands))
    )
    monkeypatch.setattr(webcam_module, "import_module", lambda name: fake_mediapipe)

    hands = webcam_module._default_hands()

    assert isinstance(hands, _FakeHands)
    assert captured == {
        "max_num_hands": 1,
        "min_detection_confidence": 0.6,
        "min_tracking_confidence": 0.5,
    }


class _FakeCv2Color:
    COLOR_BGR2RGB = 4

    @staticmethod
    def cvtColor(frame: np.ndarray, code: int) -> np.ndarray:
        assert code == _FakeCv2Color.COLOR_BGR2RGB
        return frame


def test_classify_hand_frame_reports_no_gesture_when_nothing_detected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(webcam_module, "import_module", lambda name: _FakeCv2Color())
    fake_result = types.SimpleNamespace(multi_hand_landmarks=[], multi_handedness=[])
    fake_hands = types.SimpleNamespace(process=lambda rgb: fake_result)

    candidate = classify_hand_frame(np.zeros((2, 2, 3), dtype=np.uint8), fake_hands)

    assert candidate == GestureCandidate(gesture_id=None)


def test_classify_hand_frame_classifies_a_mediapipe_style_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercises the real conversion from mediapipe's own landmark/
    handedness objects (attribute access, not the `HandLandmark` dataclass
    the rest of this module uses) into a `GestureCandidate` -- the one path
    `_landmarks()`'s fixtures above never reach, since they build
    `HandLandmark` instances directly.
    """

    monkeypatch.setattr(webcam_module, "import_module", lambda name: _FakeCv2Color())
    landmark_points = [types.SimpleNamespace(x=0.5, y=0.5) for _ in range(21)]
    for tip, pip in zip((8, 12, 16, 20), (6, 10, 14, 18), strict=True):
        landmark_points[tip] = types.SimpleNamespace(x=0.5, y=0.4)
        landmark_points[pip] = types.SimpleNamespace(x=0.5, y=0.5)
    landmark_points[4] = types.SimpleNamespace(x=0.4, y=0.5)
    landmark_points[3] = types.SimpleNamespace(x=0.5, y=0.5)
    fake_result = types.SimpleNamespace(
        multi_hand_landmarks=[types.SimpleNamespace(landmark=landmark_points)],
        multi_handedness=[
            types.SimpleNamespace(classification=[types.SimpleNamespace(label="Right", score=0.87)])
        ],
    )
    fake_hands = types.SimpleNamespace(process=lambda rgb: fake_result)

    candidate = classify_hand_frame(np.zeros((2, 2, 3), dtype=np.uint8), fake_hands)

    assert candidate == GestureCandidate(gesture_id="open_palm", hand="right", confidence=0.87)


def test_adapter_builds_the_real_default_hands_and_closes_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed = False

    class _FakeHands:
        def close(self) -> None:
            nonlocal closed
            closed = True

    monkeypatch.setattr(webcam_module, "_default_hands", lambda: _FakeHands())
    source = _FakeFrameSource([])

    adapter = WebcamLandmarkAdapter(frame_source=source)
    adapter.close()

    assert closed is True
    assert source.released is True
