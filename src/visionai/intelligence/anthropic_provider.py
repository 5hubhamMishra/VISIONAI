"""Real `LLMProvider` backed by the Anthropic API.

`anthropic` is only imported inside the constructor that touches it, so
`visionai.intelligence`/`visionai.runtime` stay importable without the
`intelligence` extra installed, mirroring `visionai.platform.webcam`'s
lazy-import pattern for `cv2`/`mediapipe`. The client itself is injectable
for tests, matching `WebcamLandmarkAdapter`'s injectable frame source and
classifier -- the automated suite never needs a real API key or network
call.
"""

from __future__ import annotations

from typing import Any

from visionai.core.errors import ProviderError
from visionai.intelligence.provider import LLMQuery, LLMReply

_SYSTEM_PROMPT = (
    "You are a conversational assistant embedded in a desktop application. "
    "You can only talk -- you have no ability to run code, open applications, "
    "browse the web, control the operating system, or take any action. Never "
    "claim to have done or changed anything. If asked to perform an action, "
    "explain that you can only answer questions."
)


class AnthropicProvider:
    """Sends one question to the Anthropic Messages API and returns the text reply."""

    def __init__(self, *, api_key: str, model: str, client: Any | None = None) -> None:
        if client is not None:
            self._client = client
        else:
            import anthropic as anthropic_module

            self._client = anthropic_module.Anthropic(api_key=api_key)
        self._model = model

    def respond(self, query: LLMQuery) -> LLMReply:
        # Broad catch is deliberate here, matching WindowsLockStateAdapter's
        # precedent: this is the true external-I/O boundary (a network call
        # to a third-party API), not application logic, so any failure --
        # including one from an injected fake client in tests, which may not
        # even be an `anthropic` exception type, and including `LLMReply`
        # rejecting a reply that fails `SafeText` validation (e.g. an
        # embedded bidi-override or invisible character) -- becomes a
        # domain error rather than a raw exception leaking past this class.
        # Catching only `anthropic.APIError` would also force importing
        # `anthropic` here even when a fake client is injected, defeating
        # the point of the injection seam.
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": query.text}],
            )
            text = next((block.text for block in response.content if block.type == "text"), "")
            return LLMReply(text=text)
        except Exception as exc:
            raise ProviderError(f"LLM provider request failed: {exc}") from exc
