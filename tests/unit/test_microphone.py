"""Tests for MicrophoneCapture and device listing: real audio boundary.

`MicrophoneCapture` itself is fully injectable (a fake `stream_factory`
stands in for real PortAudio), so these tests never touch real hardware.
`list_input_devices()` does call the real `sounddevice`/PortAudio backend
-- it has no injection seam of its own, matching `WindowsLockStateAdapter`'s
real-API smoke test rather than asserting specific device counts, since
the test runner's actual audio hardware is not under our control.
"""

from __future__ import annotations

import types

import numpy as np
import pytest

import visionai.platform.microphone as microphone_module
from visionai.config.user_settings import UserSettingsStore
from visionai.platform.microphone import (
    MicrophoneCapture,
    MicrophoneCaptureError,
    MicrophoneDevice,
    default_microphone_capture,
    list_input_devices,
)


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


def test_start_then_stop_returns_concatenated_frames() -> None:
    frames = [np.array([0.1, 0.2], dtype=np.float32), np.array([0.3], dtype=np.float32)]
    capture = MicrophoneCapture(stream_factory=_factory(frames))

    capture.start()
    audio = capture.stop()

    assert audio.tolist() == pytest.approx([0.1, 0.2, 0.3])
    assert capture._frames == []


@pytest.mark.parametrize("stage", ["start", "stop", "close"])
def test_stream_failure_releases_audio_and_allows_retry(stage: str) -> None:
    closed: list[bool] = []

    class BrokenStream(_FakeStream):
        def start(self) -> None:
            super().start()
            if stage == "start":
                raise RuntimeError("start failed")

        def stop(self) -> None:
            if stage == "stop":
                raise RuntimeError("stop failed")

        def close(self) -> None:
            closed.append(True)
            if stage == "close":
                raise RuntimeError("close failed")

    capture = MicrophoneCapture(stream_factory=lambda rate, device, callback: BrokenStream(
        callback, [np.array([0.5], dtype=np.float32)]
    ))
    with pytest.raises(RuntimeError, match=f"{stage} failed"):
        capture.start()
        capture.stop()
    assert closed == [True]
    assert capture._frames == []
    capture._stream_factory = _factory([])
    capture.start()
    assert capture.stop().size == 0


def test_overlong_capture_discards_all_audio_instead_of_transcribing_a_prefix() -> None:
    capture = MicrophoneCapture(
        sample_rate=4, max_duration_seconds=1,
        stream_factory=_factory([np.ones(4), np.ones(1), np.ones(4)]),
    )
    capture.start()
    assert capture._frames == []
    with pytest.raises(MicrophoneCaptureError, match="exceeded"):
        capture.stop()
    capture._stream_factory = _factory([np.ones(4)])
    capture.start()
    assert capture.stop().size == 4


@pytest.mark.parametrize("duration", [0, -1, float("nan"), float("inf")])
def test_capture_rejects_invalid_duration_limits(duration: float) -> None:
    with pytest.raises(ValueError):
        MicrophoneCapture(max_duration_seconds=duration)


@pytest.mark.parametrize("sample_rate", [0, -1, True, False, 1.5, "16000"])
def test_capture_rejects_invalid_sample_rate(sample_rate: object) -> None:
    with pytest.raises(ValueError, match="sample rate"):
        MicrophoneCapture(sample_rate=sample_rate)  # type: ignore[arg-type]


def test_capture_rejects_a_duration_that_rounds_to_less_than_one_sample() -> None:
    with pytest.raises(ValueError, match="at least one sample"):
        MicrophoneCapture(sample_rate=1, max_duration_seconds=0.4)


def test_stop_with_no_frames_captured_returns_empty_array() -> None:
    capture = MicrophoneCapture(stream_factory=_factory([]))

    capture.start()
    audio = capture.stop()

    assert audio.shape == (0,)


def test_start_twice_raises() -> None:
    capture = MicrophoneCapture(stream_factory=_factory([]))
    capture.start()

    with pytest.raises(MicrophoneCaptureError):
        capture.start()


def test_stop_without_start_raises() -> None:
    capture = MicrophoneCapture(stream_factory=_factory([]))

    with pytest.raises(MicrophoneCaptureError):
        capture.stop()


def test_start_after_stop_is_allowed_again() -> None:
    capture = MicrophoneCapture(stream_factory=_factory([np.array([0.5], dtype=np.float32)]))

    capture.start()
    capture.stop()
    capture.start()
    audio = capture.stop()

    assert audio.tolist() == pytest.approx([0.5])


def test_default_stream_factory_builds_a_real_inputstream_with_the_given_parameters(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}
    received_frames: list[np.ndarray] = []

    class _FakeInputStream:
        def __init__(self, *, samplerate, channels, dtype, device, callback) -> None:
            captured["samplerate"] = samplerate
            captured["channels"] = channels
            captured["dtype"] = dtype
            captured["device"] = device
            self._callback = callback

    fake_sounddevice = types.SimpleNamespace(InputStream=_FakeInputStream)
    monkeypatch.setattr(microphone_module, "import_module", lambda name: fake_sounddevice)

    stream = microphone_module._default_stream_factory(16_000, 3, received_frames.append)

    assert isinstance(stream, _FakeInputStream)
    assert captured == {
        "samplerate": 16_000,
        "channels": 1,
        "dtype": "float32",
        "device": 3,
    }

    indata = np.array([0.5, 0.25], dtype=np.float32)
    stream._callback(indata, 2, object(), object())
    indata[0] = 999.0

    assert len(received_frames) == 1
    assert received_frames[0].tolist() == [0.5, 0.25]


def test_list_input_devices_runs_against_the_real_backend() -> None:
    """Smoke test against the real PortAudio backend.

    Cannot assert a specific device or count -- the test runner's actual
    audio hardware is not under our control -- only that the real
    sounddevice.query_devices() call executes cleanly and every returned
    entry is a well-formed MicrophoneDevice with a real input channel.
    """

    devices = list_input_devices()

    assert isinstance(devices, list)
    for device in devices:
        assert isinstance(device, MicrophoneDevice)
        assert device.max_input_channels > 0


def test_default_microphone_capture_uses_saved_device(tmp_path) -> None:
    store = UserSettingsStore(tmp_path / "settings.json")
    store.set_microphone_device_index(4)

    capture = default_microphone_capture(store)

    assert capture._device == 4
