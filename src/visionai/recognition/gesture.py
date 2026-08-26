"""Deterministic temporal voting over single-frame gesture candidates.

Real camera capture and per-frame landmark classification are later phases;
this module only turns a stream of already-classified single-frame gesture
candidates into a confirmed `GestureVote`, requiring the same gesture to
hold steady for a minimum duration and enforcing a cooldown before it can
fire again. This is the safety gate approved next task 4 requires before any
gesture reaches `InputAdapter.publish_gesture()`: a camera/landmark
classifier that jitters, briefly misfires, or repeats every frame can never
turn into an action on its own.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic
from typing import Literal


@dataclass(frozen=True, slots=True)
class GestureVote:
    """One accepted, temporally-voted gesture ready to publish."""

    gesture_id: str
    hand: Literal["left", "right"]
    confidence: float
    hold_ms: int


class TemporalGestureRecognizer:
    """Votes a stream of raw single-frame candidates into confirmed gestures.

    Not thread-safe -- intended for one sequential per-frame call site (a
    single camera-processing loop), the same way `TextCommandPlanner` and
    `ConfirmationService` are each driven from one sequential orchestration
    path rather than called concurrently.
    """

    def __init__(
        self,
        *,
        min_hold_ms: int = 400,
        min_confidence: float = 0.6,
        cooldown_ms: int = 1000,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if min_hold_ms <= 0:
            raise ValueError("min_hold_ms must be greater than zero")
        if cooldown_ms < 0:
            raise ValueError("cooldown_ms must not be negative")
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence must be between 0.0 and 1.0")
        self._min_hold_ms = min_hold_ms
        self._min_confidence = min_confidence
        self._cooldown_ms = cooldown_ms
        self._clock = clock
        self._streak_key: tuple[str, str] | None = None
        self._streak_started_at: float | None = None
        self._cooldown_until: dict[tuple[str, str], float] = {}

    def observe(
        self,
        gesture_id: str | None,
        *,
        hand: Literal["left", "right"] = "right",
        confidence: float = 0.0,
    ) -> GestureVote | None:
        """Feed one single-frame candidate; return a vote only once confirmed.

        `gesture_id=None` (nothing recognized this frame) or a confidence
        below `min_confidence` rejects the candidate and resets any
        in-progress hold streak. A hand/gesture change also restarts the
        streak rather than voting on a mix of different gestures.
        """

        now = self._clock()
        if gesture_id is None or confidence < self._min_confidence:
            self._streak_key = None
            self._streak_started_at = None
            return None

        key = (gesture_id, hand)
        if key != self._streak_key or self._streak_started_at is None:
            self._streak_key = key
            self._streak_started_at = now
            return None

        held_ms = (now - self._streak_started_at) * 1000
        if held_ms < self._min_hold_ms:
            return None

        cooldown_until = self._cooldown_until.get(key)
        if cooldown_until is not None and now < cooldown_until:
            return None

        self._cooldown_until[key] = now + self._cooldown_ms / 1000
        self._streak_key = None
        self._streak_started_at = None
        return GestureVote(
            gesture_id=gesture_id, hand=hand, confidence=confidence, hold_ms=int(held_ms)
        )
