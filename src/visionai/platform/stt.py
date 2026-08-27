"""Local speech-to-text adapter backed by faster-whisper."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from importlib import import_module
from typing import Protocol, cast

import numpy as np

from visionai.config.settings import SttComputeType, SttDevice, get_settings
from visionai.core.errors import VisionAIError


class SpeechToTextError(VisionAIError):
    """Raised when the local STT provider cannot transcribe audio."""


class _Segment(Protocol):
    text: str


class _WhisperModel(Protocol):
    def transcribe(
        self, audio: np.ndarray, *, language: str, vad_filter: bool
    ) -> tuple[Iterable[_Segment], object]: ...


ModelFactory = Callable[[str, SttDevice, SttComputeType], _WhisperModel]


def _default_model_factory(
    model_size: str, device: SttDevice, compute_type: SttComputeType
) -> _WhisperModel:
    try:
        whisper = import_module("faster_whisper")
        return cast(
            _WhisperModel,
            whisper.WhisperModel(model_size, device=device, compute_type=compute_type),
        )
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        raise SpeechToTextError(
            "faster-whisper is unavailable; install the voice extra before using the microphone"
        ) from exc


class FasterWhisperTranscriber:
    """Transcribe one in-memory audio array with a lazily loaded local model."""

    def __init__(
        self,
        *,
        model_size: str = "base.en",
        device: SttDevice = "cpu",
        compute_type: SttComputeType = "int8",
        model_factory: ModelFactory = _default_model_factory,
    ) -> None:
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self._model_factory = model_factory
        self._model: _WhisperModel | None = None

    def __call__(self, audio: np.ndarray) -> str:
        if audio.size == 0:
            return ""
        if self._model is None:
            self._model = self._model_factory(
                self._model_size, self._device, self._compute_type
            )
        try:
            segments, _ = self._model.transcribe(audio, language="en", vad_filter=True)
            return " ".join(segment.text.strip() for segment in segments if segment.text.strip())
        except (OSError, RuntimeError, ValueError) as exc:
            raise SpeechToTextError("local speech-to-text failed") from exc


def default_transcriber() -> FasterWhisperTranscriber:
    """Build the configured local transcriber; the model loads on first use."""

    settings = get_settings()
    return FasterWhisperTranscriber(
        model_size=settings.stt_model_size,
        device=settings.stt_device,
        compute_type=settings.stt_compute_type,
    )
