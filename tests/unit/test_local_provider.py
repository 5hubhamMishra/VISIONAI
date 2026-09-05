"""Tests for `LocalLlamaProvider` using an injected fake client -- no real
model file, GPU, or the `gpt4all` package required."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

import visionai.intelligence.local_provider as local_provider
from visionai.core.errors import ProviderError
from visionai.intelligence.local_provider import LocalLlamaProvider
from visionai.intelligence.provider import LLMQuery


@dataclass
class _FakeModel:
    reply_text: str = "42"
    captured_kwargs: dict[str, Any] = field(default_factory=dict)

    def generate(self, prompt: str, **kwargs: Any) -> str:
        self.captured_kwargs = {"prompt": prompt, **kwargs}
        return self.reply_text


class _BrokenModel:
    def generate(self, prompt: str, **kwargs: Any) -> str:
        raise RuntimeError("model failed to load")


def test_constructor_loads_existing_model_without_download(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class _Gpt4All:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

        def generate(self, prompt: str, **kwargs: Any) -> str:
            return "ok"

    class _Gpt4AllModule:
        GPT4All = _Gpt4All

    monkeypatch.setattr(local_provider, "import_module", lambda name: _Gpt4AllModule())

    LocalLlamaProvider(model_path=r"C:\models\assistant.gguf")

    assert captured == {
        "model_name": "assistant.gguf",
        "model_path": r"C:\models",
        "allow_download": False,
    }


def test_respond_returns_the_generated_text() -> None:
    client = _FakeModel(reply_text="the answer is 42")
    provider = LocalLlamaProvider(model_path="unused.gguf", client=client)

    reply = provider.respond(LLMQuery(text="what is the answer?"))

    assert reply.text == "the answer is 42"


def test_respond_strips_surrounding_whitespace_from_the_reply() -> None:
    client = _FakeModel(reply_text="  padded reply  \n")
    provider = LocalLlamaProvider(model_path="unused.gguf", client=client)

    reply = provider.respond(LLMQuery(text="hello"))

    assert reply.text == "padded reply"


def test_respond_sends_the_question_inside_the_prompt() -> None:
    client = _FakeModel()
    provider = LocalLlamaProvider(model_path="unused.gguf", client=client)

    provider.respond(LLMQuery(text="hello there"))

    assert "hello there" in client.captured_kwargs["prompt"]
    assert client.captured_kwargs["max_tokens"] == 512


def test_respond_wraps_a_client_failure_as_provider_error() -> None:
    provider = LocalLlamaProvider(model_path="unused.gguf", client=_BrokenModel())

    with pytest.raises(ProviderError):
        provider.respond(LLMQuery(text="hello"))


def test_respond_wraps_an_unsafe_reply_as_provider_error_not_a_raw_validation_error() -> None:
    """Matches `AnthropicProvider`'s equivalent regression test: a reply
    containing a bidi-override or other character `LLMReply`'s `SafeText`
    field rejects must become the same domain error every other failure at
    this boundary does, not a raw `pydantic.ValidationError`."""

    client = _FakeModel(reply_text="cats\u202ereversed")
    provider = LocalLlamaProvider(model_path="unused.gguf", client=client)

    with pytest.raises(ProviderError):
        provider.respond(LLMQuery(text="hello"))
