"""Tests for GestureCaptureLoop: camera adapter -> temporal voting -> input bus."""

from __future__ import annotations

import pytest

from visionai.core.event_bus import EventBus
from visionai.core.events import GestureEvent
from visionai.orchestration.event_orchestrator import InputAdapter
from visionai.platform.camera import GestureCandidate, StaticLandmarkAdapter
from visionai.recognition.capture import GestureCaptureLoop
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
