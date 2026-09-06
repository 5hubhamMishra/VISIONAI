from __future__ import annotations

import types

import numpy as np
import pytest

import visionai.platform.stt as stt_module
from visionai.platform.stt import FasterWhisperTranscriber, SpeechToTextError


class _Segment:
    def __init__(self, text: str) -> None:
        self.text = text


class _Model:
    def __init__(self) -> None:
        self.calls = 0

    def transcribe(self, audio, *, language: str, vad_filter: bool):
        self.calls += 1
        assert audio.dtype == np.float32
        assert language == "en"
        assert vad_filter is True
        return iter([_Segment(" open"), _Segment(" notepad "), _Segment(" ")]), object()


def test_faster_whisper_transcriber_loads_once_and_joins_segments() -> None:
    model = _Model()
    transcriber = FasterWhisperTranscriber(model_factory=lambda *_: model)
    audio = np.array([0.1, 0.2], dtype=np.float32)

    assert transcriber(audio) == "open notepad"
    assert transcriber(audio) == "open notepad"
    assert model.calls == 2


def test_faster_whisper_transcriber_skips_empty_audio() -> None:
    created = []
    transcriber = FasterWhisperTranscriber(model_factory=lambda *_: created.append(True))

    assert transcriber(np.empty((0,), dtype=np.float32)) == ""
    assert created == []


def test_transcribe_wraps_model_failure_as_speechtotexterror() -> None:
    class _FailingModel:
        def transcribe(self, audio, *, language: str, vad_filter: bool):
            raise RuntimeError("model exploded")

    transcriber = FasterWhisperTranscriber(model_factory=lambda *_: _FailingModel())
    audio = np.array([0.1], dtype=np.float32)

    with pytest.raises(SpeechToTextError, match="local speech-to-text failed") as excinfo:
        transcriber(audio)
    assert isinstance(excinfo.value.__cause__, RuntimeError)


def test_default_model_factory_raises_speechtotexterror_when_faster_whisper_missing(
    monkeypatch,
) -> None:
    def raise_import_error(name: str) -> None:
        raise ImportError(f"No module named '{name}'")

    monkeypatch.setattr(stt_module, "import_module", raise_import_error)

    with pytest.raises(SpeechToTextError, match="faster-whisper is unavailable") as excinfo:
        stt_module._default_model_factory("base.en", "cpu", "int8")
    assert isinstance(excinfo.value.__cause__, ImportError)


def test_default_transcriber_builds_the_real_model_factory_from_settings(monkeypatch) -> None:
    fake_settings = types.SimpleNamespace(
        stt_model_size="small.en", stt_device="cuda", stt_compute_type="float16"
    )
    monkeypatch.setattr(stt_module, "get_settings", lambda: fake_settings)

    captured: dict[str, object] = {}

    class _FakeWhisperModel:
        def __init__(self, model_size: str, device: str, compute_type: str) -> None:
            captured["model_size"] = model_size
            captured["device"] = device
            captured["compute_type"] = compute_type

        def transcribe(self, audio, *, language: str, vad_filter: bool):
            return iter([]), object()

    fake_module = types.SimpleNamespace(WhisperModel=_FakeWhisperModel)
    monkeypatch.setattr(stt_module, "import_module", lambda name: fake_module)

    transcriber = stt_module.default_transcriber()

    assert transcriber(np.array([0.1], dtype=np.float32)) == ""
    assert captured == {
        "model_size": "small.en",
        "device": "cuda",
        "compute_type": "float16",
    }
