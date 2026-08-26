"""Tests for the camera/landmark adapter boundary."""

from __future__ import annotations

from visionai.platform.camera import GestureCandidate, StaticLandmarkAdapter


def test_replays_candidates_in_order() -> None:
    adapter = StaticLandmarkAdapter(
        candidates=[
            GestureCandidate(gesture_id="pinch", hand="right", confidence=0.9),
            GestureCandidate(gesture_id="swipe_left", hand="left", confidence=0.8),
        ]
    )

    assert adapter.read_candidate() == GestureCandidate(
        gesture_id="pinch", hand="right", confidence=0.9
    )
    assert adapter.read_candidate() == GestureCandidate(
        gesture_id="swipe_left", hand="left", confidence=0.8
    )


def test_returns_none_gesture_once_exhausted() -> None:
    adapter = StaticLandmarkAdapter(
        candidates=[GestureCandidate(gesture_id="pinch", confidence=0.9)]
    )

    adapter.read_candidate()

    assert adapter.read_candidate() == GestureCandidate(gesture_id=None)
    assert adapter.read_candidate() == GestureCandidate(gesture_id=None)


def test_empty_adapter_always_returns_none_gesture() -> None:
    adapter = StaticLandmarkAdapter()

    assert adapter.read_candidate().gesture_id is None
