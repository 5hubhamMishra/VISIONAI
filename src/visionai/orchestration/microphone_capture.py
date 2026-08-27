"""Real press/release microphone capture bridged into the voice event boundary.

Not re-exported from `visionai.orchestration.__init__`: it depends on
`numpy` (the optional `voice` extra, via `visionai.platform.microphone`),
and the rest of the orchestration package must stay importable for anyone
who has not installed that extra. Import it directly:
`from visionai.orchestration.microphone_capture import MicrophonePushToTalk`.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from visionai.core.events import TranscriptEvent
from visionai.orchestration.event_orchestrator import InputAdapter
from visionai.platform.microphone import MicrophoneCapture, default_microphone_capture


class MicrophonePushToTalk:
    """Starts real recording on press, transcribes and publishes on release.

    Mirrors `PushToTalkRunner`'s press/release contract, but owns a real
    `MicrophoneCapture` so recording genuinely starts and stops in step
    with the button rather than assuming capture already happened
    elsewhere. `transcribe` receives the recorded samples and returns
    text -- the same kind of injected, non-bundled STT boundary
    `InputAdapter.publish_voice_capture()` already uses, just fed real
    audio instead of being called with no arguments.
    """

    def __init__(
        self,
        *,
        input_adapter: InputAdapter,
        capture: MicrophoneCapture | None = None,
        transcribe: Callable[[np.ndarray], str],
        confidence: float = 1.0,
        language: str = "en",
    ) -> None:
        self._input_adapter = input_adapter
        self._capture = capture if capture is not None else default_microphone_capture()
        self._transcribe = transcribe
        self._confidence = confidence
        self._language = language
        self._recording = False

    def press(self) -> bool:
        """Start real recording; return False if already recording."""

        if self._recording:
            return False
        self._capture.start()
        self._recording = True
        return True

    async def release(self) -> TranscriptEvent | None:
        """Stop recording and publish exactly one final transcript.

        Returns `None` if nothing was recording, matching
        `PushToTalkRunner.release()`'s no-op-without-press behavior.
        """

        if not self._recording:
            return None
        self._recording = False
        audio = self._capture.stop()
        return await self._input_adapter.publish_voice_capture(
            lambda: self._transcribe(audio),
            confidence=self._confidence,
            language=self._language,
        )
