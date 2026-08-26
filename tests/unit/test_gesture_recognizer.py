"""Tests for temporal gesture voting: hold, rejection, and cooldown."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from visionai.recognition.gesture import GestureVote, TemporalGestureRecognizer


def _clock(times: list[float]) -> Callable[[], float]:
    values = iter(times)

    def _next() -> float:
        return next(values)

    return _next


def test_rejects_below_min_confidence() -> None:
    recognizer = TemporalGestureRecognizer(min_confidence=0.6, clock=_clock([0.0]))

    assert recognizer.observe("swipe_left", confidence=0.4) is None


def test_rejects_no_gesture_this_frame() -> None:
    recognizer = TemporalGestureRecognizer(clock=_clock([0.0]))

    assert recognizer.observe(None, confidence=0.9) is None


def test_first_observation_starts_streak_without_voting() -> None:
    recognizer = TemporalGestureRecognizer(min_hold_ms=400, clock=_clock([0.0]))

    assert recognizer.observe("swipe_left", confidence=0.9) is None


def test_votes_once_hold_duration_is_reached() -> None:
    recognizer = TemporalGestureRecognizer(min_hold_ms=400, clock=_clock([0.0, 0.1, 0.45]))

    assert recognizer.observe("swipe_left", confidence=0.9) is None
    assert recognizer.observe("swipe_left", confidence=0.9) is None
    vote = recognizer.observe("swipe_left", confidence=0.9)

    assert vote == GestureVote(gesture_id="swipe_left", hand="right", confidence=0.9, hold_ms=450)


def test_gesture_change_restarts_the_streak() -> None:
    recognizer = TemporalGestureRecognizer(min_hold_ms=400, clock=_clock([0.0, 0.5, 0.6, 1.0]))

    assert recognizer.observe("swipe_left", confidence=0.9) is None
    assert recognizer.observe("swipe_right", confidence=0.9) is None
    assert recognizer.observe("swipe_right", confidence=0.9) is None
    vote = recognizer.observe("swipe_right", confidence=0.9)

    assert vote is not None
    assert vote.gesture_id == "swipe_right"


def test_low_confidence_frame_resets_an_in_progress_streak() -> None:
    recognizer = TemporalGestureRecognizer(
        min_hold_ms=400, min_confidence=0.6, clock=_clock([0.0, 0.5, 0.6, 0.9])
    )

    assert recognizer.observe("swipe_left", confidence=0.9) is None
    assert recognizer.observe("swipe_left", confidence=0.2) is None
    assert recognizer.observe("swipe_left", confidence=0.9) is None
    # Streak restarted at t=0.6; only 300ms elapsed by t=0.9, still short of the hold.
    assert recognizer.observe("swipe_left", confidence=0.9) is None


def test_cooldown_blocks_immediate_re_vote_of_the_same_gesture() -> None:
    recognizer = TemporalGestureRecognizer(
        min_hold_ms=400, cooldown_ms=1000, clock=_clock([0.0, 0.5, 0.6, 1.0])
    )

    assert recognizer.observe("swipe_left", confidence=0.9) is None
    assert recognizer.observe("swipe_left", confidence=0.9) is not None
    assert recognizer.observe("swipe_left", confidence=0.9) is None
    assert recognizer.observe("swipe_left", confidence=0.9) is None


def test_cooldown_expires_and_allows_a_later_re_vote() -> None:
    recognizer = TemporalGestureRecognizer(
        min_hold_ms=400, cooldown_ms=1000, clock=_clock([0.0, 0.5, 2.0, 2.5])
    )

    assert recognizer.observe("swipe_left", confidence=0.9) is None
    assert recognizer.observe("swipe_left", confidence=0.9) is not None
    assert recognizer.observe("swipe_left", confidence=0.9) is None
    vote = recognizer.observe("swipe_left", confidence=0.9)
    assert vote is not None


@pytest.mark.parametrize(
    "bad_kwargs", [{"min_hold_ms": 0}, {"cooldown_ms": -1}, {"min_confidence": 1.5}]
)
def test_rejects_invalid_construction(bad_kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        TemporalGestureRecognizer(**bad_kwargs)
