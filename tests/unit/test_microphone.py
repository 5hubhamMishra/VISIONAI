"""Tests for MicrophoneCapture and device listing: real audio boundary.

`MicrophoneCapture` itself is fully injectable (a fake `stream_factory`
stands in for real PortAudio), so these tests never touch real hardware.
`list_input_devices()` does call the real `sounddevice`/PortAudio backend
-- it has no injection seam of its own, matching `WindowsLockStateAdapter`'s
real-API smoke test rather than asserting specific device counts, since
the test runner's actual audio hardware is not under our control.
"""

from __future__ import annotations

import numpy as np
import pytest

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
