"""Real `LLMProvider` backed by a local, offline GGUF model via `gpt4all`.

Mirrors `visionai.intelligence.anthropic_provider`'s shape: `gpt4all` is only
imported inside the constructor that touches it, so `visionai.intelligence`/
`visionai.runtime` stay importable without the `local_llm` extra installed.
The client itself is injectable for tests, matching `AnthropicProvider`'s
injectable client and `WebcamLandmarkAdapter`'s injectable frame source --
the automated suite never needs a real model file, GPU, or network access.

This provider never downloads a model: the real client is always
constructed with `allow_download=False`, so a missing or misconfigured
model path fails loudly with a clear error instead of silently reaching
the network -- the one thing that would make a "local/offline" provider
indistinguishable from a cloud one from a privacy/network standpoint. The
model file itself must already exist on disk; fetching one is a user
action outside this application, never something this code does on a
user's behalf.
"""

from __future__ import annotations

from importlib import import_module
from pathlib import PureWindowsPath
from typing import Protocol

from visionai.core.errors import ProviderError
from visionai.intelligence.provider import LLMQuery, LLMReply

_SYSTEM_PROMPT = (
    "You are a conversational assistant embedded in a desktop application. "
    "You can only talk -- you have no ability to run code, open applications, "
    "browse the web, control the operating system, or take any action. Never "
    "claim to have done or changed anything. If asked to perform an action, "
    "explain that you can only answer questions."
)
_MAX_TOKENS = 512


class _LocalModel(Protocol):
    """The subset of `gpt4all.GPT4All`'s public API this provider calls."""

    def generate(self, prompt: str, *, max_tokens: int) -> str: ...


class LocalLlamaProvider:
    """Sends one question to a local GGUF model file and returns the text reply."""

    def __init__(self, *, model_path: str, client: _LocalModel | None = None) -> None:
        if client is not None:
            self._client = client
        else:
            gpt4all = import_module("gpt4all")
            # `PureWindowsPath`, not `pathlib.Path`: this application only ships
            # on Windows, and using the ambient `Path` flavor made this split
            # silently depend on the host OS running the code (a Windows path
            # would parse as a single opaque filename with an empty parent on
            # a POSIX host), which is untestable outside Windows and was never
            # actually exercised there before this was found.
            path = PureWindowsPath(model_path)
            self._client = gpt4all.GPT4All(
                model_name=path.name,
                model_path=str(path.parent),
                allow_download=False,
            )

    def respond(self, query: LLMQuery) -> LLMReply:
        # Broad catch is deliberate here, matching `AnthropicProvider.respond()`'s
        # precedent: this is the true external-I/O boundary (a local model
        # load/inference call), not application logic, so any failure --
        # including one from an injected fake client in tests, and including
        # `LLMReply` rejecting a reply that fails `SafeText` validation --
        # becomes a domain error rather than a raw exception leaking past
        # this class.
        try:
            prompt = f"{_SYSTEM_PROMPT}\n\nUser: {query.text}\nAssistant:"
            text = self._client.generate(prompt, max_tokens=_MAX_TOKENS)
            return LLMReply(text=text.strip())
        except Exception as exc:
            raise ProviderError(f"Local LLM provider request failed: {exc}") from exc
