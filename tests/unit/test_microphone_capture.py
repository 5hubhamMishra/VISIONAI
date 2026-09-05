"""Tests for MicrophonePushToTalk: real press/release timing over a fake stream."""

from __future__ import annotations

import numpy as np
import pytest

from visionai.core.event_bus import EventBus
from visionai.orchestration.event_orchestrator import InputAdapter
from visionai.orchestration.microphone_capture import MicrophonePushToTalk
from visionai.platform.microphone import MicrophoneCapture


class _FakeStream:
    def __init__(self, on_audio, frames: list[np.ndarray]) -> None:
        self._on_audio = on_audio
        self._frames = frames

    def start(self) -> None:
        for frame in self._frames:
            self._on_audio(frame)

    def stop(self) -> None:
        pass

    def close(self) -> None:
        pass


def _factory(frames: list[np.ndarray]):
    def factory(sample_rate: int, device: int | None, on_audio):
        return _FakeStream(on_audio, frames)

    return factory


@pytest.mark.asyncio
async def test_release_transcribes_recorded_audio_and_publishes_once() -> None:
    bus = EventBus(max_size=10)
    input_adapter = InputAdapter(input_bus=bus)
    capture = MicrophoneCapture(stream_factory=_factory([np.array([0.1, 0.2], dtype=np.float32)]))
    seen_audio: list[np.ndarray] = []

    def transcribe(audio: np.ndarray) -> str:
        seen_audio.append(audio)
        return "open notepad"

    runner = MicrophonePushToTalk(
        input_adapter=input_adapter, capture=capture, transcribe=transcribe
    )

    assert runner.press() is True
    event = await runner.release()

    assert event is not None
    assert event.text == "open notepad"
    assert event.is_final is True
    assert bus.size == 1
    assert seen_audio[0].tolist() == pytest.approx([0.1, 0.2])


@pytest.mark.asyncio
async def test_duplicate_press_is_ignored() -> None:
    bus = EventBus(max_size=10)
    input_adapter = InputAdapter(input_bus=bus)
    capture = MicrophoneCapture(stream_factory=_factory([]))
    runner = MicrophonePushToTalk(
        input_adapter=input_adapter, capture=capture, transcribe=lambda audio: "x"
    )

    assert runner.press() is True
    assert runner.press() is False

    await runner.release()


@pytest.mark.asyncio
async def test_release_without_press_is_a_noop() -> None:
    bus = EventBus(max_size=10)
    input_adapter = InputAdapter(input_bus=bus)
    capture = MicrophoneCapture(stream_factory=_factory([]))
    runner = MicrophonePushToTalk(
        input_adapter=input_adapter, capture=capture, transcribe=lambda audio: "x"
    )

    result = await runner.release()

    assert result is None
    assert bus.size == 0


@pytest.mark.asyncio
async def test_release_after_release_is_a_noop() -> None:
    bus = EventBus(max_size=10)
    input_adapter = InputAdapter(input_bus=bus)
    capture = MicrophoneCapture(stream_factory=_factory([np.array([0.4], dtype=np.float32)]))
    runner = MicrophonePushToTalk(
        input_adapter=input_adapter, capture=capture, transcribe=lambda audio: "open notepad"
    )

    runner.press()
    first = await runner.release()
    second = await runner.release()

    assert first is not None
    assert second is None
    assert bus.size == 1


async def test_cancel_discards_recording_without_transcription_and_allows_retry() -> None:
    bus = EventBus(max_size=10)
    capture = MicrophoneCapture(stream_factory=_factory([np.array([0.4], dtype=np.float32)]))
    transcribed: list[bool] = []

    def transcribe(audio: np.ndarray) -> str:
        transcribed.append(True)
        return "open notepad"

    runner = MicrophonePushToTalk(
        input_adapter=InputAdapter(bus), capture=capture, transcribe=transcribe
    )
    assert not runner.cancel()
    runner.press()
    assert runner.cancel()
    assert await runner.release() is None
    assert transcribed == []
    assert bus.size == 0
    assert capture._frames == []
    assert runner.press()
    assert await runner.release() is not None
    assert transcribed == [True]


def test_capture_defaults_to_saved_microphone_factory(monkeypatch) -> None:
    expected = MicrophoneCapture(stream_factory=_factory([]))
    monkeypatch.setattr(
        "visionai.orchestration.microphone_capture.default_microphone_capture",
        lambda: expected,
    )
    input_adapter = InputAdapter(input_bus=EventBus(max_size=10))

    runner = MicrophonePushToTalk(input_adapter=input_adapter, transcribe=lambda audio: "")

    assert runner._capture is expected
