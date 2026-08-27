from __future__ import annotations

import numpy as np

from visionai.platform.stt import FasterWhisperTranscriber


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
