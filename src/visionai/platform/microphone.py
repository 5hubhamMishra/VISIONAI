"""Real microphone device selection and push-to-talk audio capture.

Uses `sounddevice` (PortAudio bindings) for real device enumeration and
recording. Captured audio lives only in memory for the duration of one
start()/stop() capture and is handed back to the caller as a plain
`numpy` array -- never written to disk or published as a raw-audio event,
matching this project's "no raw audio in events/storage" invariant.
Speech-to-text stays out of scope here: callers supply their own
transcriber, the same way `InputAdapter.publish_voice_capture()` already
takes an injected transcriber rather than bundling a specific STT engine.

`sounddevice` is only imported inside `_default_stream_factory()` and
`list_input_devices()`, not at module import time, so importing this
module -- and any test that injects its own `stream_factory` -- never
requires the real PortAudio backend or an attached device to be present.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from math import isfinite
from typing import Protocol

import numpy as np

from visionai.config.user_settings import UserSettingsStore, default_user_settings_store
from visionai.core.errors import VisionAIError

DEFAULT_SAMPLE_RATE = 16_000


class MicrophoneCaptureError(VisionAIError):
    """Raised when starting or stopping a capture is invalid."""


@dataclass(frozen=True, slots=True)
class MicrophoneDevice:
    """One real, selectable audio input device."""

    index: int
    name: str
    max_input_channels: int


def list_input_devices() -> list[MicrophoneDevice]:
    """Return every real audio device with at least one input channel."""

    sd = import_module("sounddevice")

    return [
        MicrophoneDevice(
            index=index, name=info["name"], max_input_channels=info["max_input_channels"]
        )
        for index, info in enumerate(sd.query_devices())
        if info.get("max_input_channels", 0) > 0
    ]


AudioCallback = Callable[[np.ndarray], None]


class AudioStream(Protocol):
    """The minimal real-time audio stream surface this module depends on."""

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def close(self) -> None: ...


StreamFactory = Callable[[int, int | None, AudioCallback], AudioStream]


def _default_stream_factory(
    sample_rate: int, device: int | None, on_audio: AudioCallback
) -> AudioStream:
    sd = import_module("sounddevice")

    def _callback(indata: np.ndarray, frames: int, time_info: object, status: object) -> None:
        on_audio(indata.copy())

    stream: AudioStream = sd.InputStream(
        samplerate=sample_rate, channels=1, dtype="float32", device=device, callback=_callback
    )
    return stream


class MicrophoneCapture:
    """Records real audio in memory between start() and stop().

    Not thread-safe, and intended for one capture at a time: calling
    start() while already recording raises rather than silently
    restarting (a dropped partial recording would be a confusing silent
    bug, not a safety issue, but still worth surfacing loudly), and
    calling stop() with nothing started raises rather than returning an
    ambiguous empty result that looks identical to "recorded silence."
    """

    def __init__(
        self,
        *,
        device: int | None = None,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        max_duration_seconds: float = 120.0,
        stream_factory: StreamFactory = _default_stream_factory,
    ) -> None:
        if isinstance(sample_rate, bool) or not isinstance(sample_rate, int) or sample_rate <= 0:
            raise ValueError("sample rate must be a positive integer")
        if not isfinite(max_duration_seconds) or max_duration_seconds <= 0:
            raise ValueError("maximum capture duration must be finite and positive")
        self._max_samples = int(sample_rate * max_duration_seconds)
        if self._max_samples < 1:
            raise ValueError("maximum capture duration must allow at least one sample")
        self._device = device
        self._sample_rate = sample_rate
        self._stream_factory = stream_factory
        self._stream: AudioStream | None = None
        self._frames: list[np.ndarray] = []
        self._sample_count = 0
        self._overflowed = False

    def _on_audio(self, frame: np.ndarray) -> None:
        if self._overflowed:
            return
        self._sample_count += frame.size
        if self._sample_count > self._max_samples:
            self._overflowed = True
            self._frames.clear()
        else:
            self._frames.append(frame)

    def start(self) -> None:
        """Begin recording; frames accumulate in memory until stop()."""

        if self._stream is not None:
            raise MicrophoneCaptureError("capture already in progress")
        self._frames.clear()
        self._sample_count = 0
        self._overflowed = False
        try:
            self._stream = self._stream_factory(self._sample_rate, self._device, self._on_audio)
            self._stream.start()
        except BaseException:
            try:
                if self._stream is not None:
                    self._stream.close()
            finally:
                self._stream = None
                self._frames.clear()
            raise

    def stop(self) -> np.ndarray:
        """End recording and return the captured samples as one array."""

        if self._stream is None:
            raise MicrophoneCaptureError("no capture in progress")
        try:
            try:
                self._stream.stop()
            finally:
                self._stream.close()
            if self._overflowed:
                raise MicrophoneCaptureError(
                    "Recording exceeded the capture limit; please record a shorter command."
                )
            if not self._frames:
                return np.empty((0,), dtype=np.float32)
            audio: np.ndarray = np.reshape(np.concatenate(self._frames, axis=0), -1)
            return audio
        finally:
            self._stream = None
            self._frames.clear()


def default_microphone_capture(
    settings_store: UserSettingsStore | None = None,
) -> MicrophoneCapture:
    """Build capture using the persisted device choice, if one exists."""

    store = settings_store or default_user_settings_store()
    return MicrophoneCapture(device=store.get_microphone_device_index())
