"""Deterministic wake-word gating over already-transcribed voice input.

Continuous microphone capture and a real hotword-spotting engine are later
phases -- this module only turns a stream of already-transcribed utterances
(injected, no raw audio) into a gated command: an utterance that does not
start with the configured wake word is silently rejected, and one that does
is published with the wake word stripped. This mirrors
`TemporalGestureRecognizer`'s "reject on the object, gate before the bus"
shape for gestures, and lets this wake-word gate coexist with
`PushToTalkRunner` as two independent activation modes over the same
`InputAdapter.publish_voice_capture()` path.
"""

from __future__ import annotations

from collections.abc import AsyncIterable
from dataclasses import dataclass, field

from visionai.config.user_settings import DEFAULT_WAKE_WORD
from visionai.core.cancellation import CancellationToken
from visionai.core.events import TranscriptEvent
from visionai.orchestration.event_orchestrator import InputAdapter


def _normalize(word: str) -> str:
    normalized = " ".join(word.split()).lower()
    if not normalized:
        raise ValueError("wake word must not be empty")
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in normalized):
        raise ValueError("wake word must not contain control characters")
    return normalized


@dataclass(frozen=True, slots=True)
class WakeWordGate:
    """Matches and strips a configured wake word from an utterance.

    Case-insensitive and whitespace-normalized; the wake word may itself be
    a phrase ("hey visionai"). Deliberately text-only, so it composes with
    any STT provider the same way `InputAdapter.publish_voice_capture()`
    already does.
    """

    wake_word: str = DEFAULT_WAKE_WORD

    def __post_init__(self) -> None:
        object.__setattr__(self, "wake_word", _normalize(self.wake_word))

    def match(self, text: str) -> str | None:
        """Return the command with the wake word stripped, or `None`.

        Returns `None` if the wake word is absent, or if it is present but
        nothing follows it -- an activation with no command is not useful
        work to publish. The remainder keeps the original casing/spacing of
        `text`; only internal run-of-whitespace is collapsed, matching
        `TextCommandPlanner`'s own normalization downstream.
        """

        words = text.split()
        wake_words = self.wake_word.split()
        if len(words) <= len(wake_words):
            return None
        head = " ".join(word.lower() for word in words[: len(wake_words)])
        if head != self.wake_word:
            return None
        return " ".join(words[len(wake_words) :])


@dataclass(slots=True)
class WakeWordVoiceRunner:
    """Gate a stream of already-transcribed utterances on a wake word.

    Mirrors `PushToTalkRunner`'s shape but has no press/release state: each
    call to `observe()` is one already-final utterance from an injected,
    continuous STT source. Only an utterance that begins with the
    configured wake word is published, with the wake word stripped;
    anything else is silently ignored, the same "most calls return None"
    shape `InputAdapter.publish_gesture_observation()` uses for noisy
    input. Real continuous capture and hotword spotting are later work, the
    same way `MicrophonePushToTalk` came after `PushToTalkRunner`.
    """

    input_adapter: InputAdapter
    gate: WakeWordGate = field(default_factory=WakeWordGate)
    confidence: float = 1.0
    language: str = "en"

    async def observe(self, utterance: str) -> TranscriptEvent | None:
        """Feed one already-transcribed utterance; publish only if gated in."""

        command = self.gate.match(utterance)
        if command is None:
            return None
        return await self.input_adapter.publish_voice_capture(
            lambda: command,
            confidence=self.confidence,
            language=self.language,
        )


@dataclass(slots=True)
class WakeWordListeningLoop:
    """Feed an async stream of final transcripts through wake-word gating.

    The source owns transcription and any hardware; this loop owns only
    cancellation and routing accepted commands to the existing input bus.
    """

    runner: WakeWordVoiceRunner
    source: AsyncIterable[str]
    cancellation: CancellationToken | None = None

    async def run(self) -> int:
        """Consume until the source ends or cancellation is requested."""

        accepted = 0
        async for utterance in self.source:
            if self.cancellation is not None and self.cancellation.is_cancelled:
                break
            if await self.runner.observe(utterance) is not None:
                accepted += 1
        return accepted
