"""Tests for GestureCaptureLoop: camera adapter -> temporal voting -> input bus."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from visionai.core.cancellation import CancellationToken
from visionai.core.event_bus import EventBus
from visionai.core.events import GestureEvent
from visionai.orchestration.event_orchestrator import InputAdapter
from visionai.platform.camera import GestureCandidate, LandmarkAdapter, StaticLandmarkAdapter
from visionai.recognition.capture import GestureCaptureLoop, GestureListeningLoop
from visionai.recognition.gesture import TemporalGestureRecognizer


@pytest.mark.asyncio
async def test_capture_once_publishes_only_once_hold_duration_is_reached() -> None:
    bus = EventBus(max_size=10)
    input_adapter = InputAdapter(input_bus=bus)
    landmark_adapter = StaticLandmarkAdapter(
        candidates=[
            GestureCandidate(gesture_id="pinch", hand="right", confidence=0.9),
            GestureCandidate(gesture_id="pinch", hand="right", confidence=0.9),
            GestureCandidate(gesture_id="pinch", hand="right", confidence=0.9),
        ]
    )
    times = iter([0.0, 0.1, 0.45])
    recognizer = TemporalGestureRecognizer(min_hold_ms=400, clock=lambda: next(times))
    loop = GestureCaptureLoop(
        landmark_adapter=landmark_adapter, recognizer=recognizer, input_adapter=input_adapter
    )

    first = await loop.capture_once()
    second = await loop.capture_once()
    third = await loop.capture_once()

    assert first is None
    assert second is None
    assert third is not None
    assert bus.size == 1
    queued = await bus.next_event()
    assert isinstance(queued, GestureEvent)
    assert queued == third


@pytest.mark.asyncio
async def test_capture_once_publishes_nothing_when_no_gesture_recognized() -> None:
    bus = EventBus(max_size=10)
    input_adapter = InputAdapter(input_bus=bus)
    landmark_adapter = StaticLandmarkAdapter()
    recognizer = TemporalGestureRecognizer()
    loop = GestureCaptureLoop(
        landmark_adapter=landmark_adapter, recognizer=recognizer, input_adapter=input_adapter
    )

    result = await loop.capture_once()

    assert result is None
    assert bus.size == 0


@dataclass
class _CancelWhenExhausted:
    """Wraps a `LandmarkAdapter` and cancels a token once `total` reads happen.

    Lets a test drive `GestureListeningLoop.run()` to a deterministic stop
    without an artificial upper bound on iterations -- the real adapter has
    no natural "done" signal either, so the loop can only ever be stopped
    by cancellation, exactly as in production.
    """

    inner: LandmarkAdapter
    token: CancellationToken
    total: int
    _count: int = field(default=0, init=False)

    def read_candidate(self) -> GestureCandidate:
        self._count += 1
        candidate = self.inner.read_candidate()
        if self._count >= self.total:
            self.token.cancel()
        return candidate


@pytest.mark.asyncio
async def test_gesture_listening_loop_counts_confirmed_votes_and_honors_cancellation() -> None:
    bus = EventBus(max_size=10)
    input_adapter = InputAdapter(input_bus=bus)
    landmark_adapter = StaticLandmarkAdapter(
        candidates=[
            GestureCandidate(gesture_id="open_palm", hand="right", confidence=0.9),
            GestureCandidate(gesture_id="open_palm", hand="right", confidence=0.9),
            GestureCandidate(gesture_id="open_palm", hand="right", confidence=0.9),
            GestureCandidate(gesture_id="closed_fist", hand="right", confidence=0.9),
            GestureCandidate(gesture_id="closed_fist", hand="right", confidence=0.9),
            GestureCandidate(gesture_id="closed_fist", hand="right", confidence=0.9),
        ]
    )
    times = iter([0.0, 0.1, 0.5, 0.6, 0.7, 1.1])
    recognizer = TemporalGestureRecognizer(min_hold_ms=400, clock=lambda: next(times))
    token = CancellationToken()
    wrapped = _CancelWhenExhausted(landmark_adapter, token, total=6)
    capture = GestureCaptureLoop(
        landmark_adapter=wrapped, recognizer=recognizer, input_adapter=input_adapter
    )

    confirmed = await GestureListeningLoop(capture, token).run()

    assert confirmed == 2
    assert bus.size == 2


@pytest.mark.asyncio
async def test_gesture_listening_loop_reads_nothing_when_already_cancelled() -> None:
    bus = EventBus(max_size=10)
    input_adapter = InputAdapter(input_bus=bus)
    landmark_adapter = StaticLandmarkAdapter(
        candidates=[GestureCandidate(gesture_id="open_palm", hand="right", confidence=0.9)]
    )
    capture = GestureCaptureLoop(
        landmark_adapter=landmark_adapter,
        recognizer=TemporalGestureRecognizer(),
        input_adapter=input_adapter,
    )
    token = CancellationToken()
    token.cancel()

    confirmed = await GestureListeningLoop(capture, token).run()

    assert confirmed == 0
    assert bus.size == 0
