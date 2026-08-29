"""Tests for `AnthropicProvider` using an injected fake client -- no real
network call, API key, or the `anthropic` package required."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest

from visionai.core.errors import ProviderError
from visionai.intelligence.anthropic_provider import AnthropicProvider
from visionai.intelligence.provider import LLMQuery


@dataclass
class _FakeMessages:
    reply_text: str = "42"
    captured_kwargs: dict[str, Any] = field(default_factory=dict)

    def create(self, **kwargs: Any) -> Any:
        self.captured_kwargs = kwargs
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self.reply_text)])


@dataclass
class _FakeClient:
    messages: _FakeMessages = field(default_factory=_FakeMessages)


class _BrokenMessages:
    def create(self, **kwargs: Any) -> Any:
        raise RuntimeError("connection failed")


def test_respond_returns_the_first_text_block() -> None:
    client = _FakeClient(messages=_FakeMessages(reply_text="the answer is 42"))
    provider = AnthropicProvider(api_key="unused", model="claude-opus-5", client=client)

    reply = provider.respond(LLMQuery(text="what is the answer?"))

    assert reply.text == "the answer is 42"


def test_respond_sends_the_configured_model_and_question() -> None:
    client = _FakeClient()
    provider = AnthropicProvider(api_key="unused", model="claude-opus-5", client=client)

    provider.respond(LLMQuery(text="hello"))

    assert client.messages.captured_kwargs["model"] == "claude-opus-5"
    assert client.messages.captured_kwargs["messages"] == [
        {"role": "user", "content": "hello"}
    ]


def test_respond_wraps_a_client_failure_as_provider_error() -> None:
    client = SimpleNamespace(messages=_BrokenMessages())
    provider = AnthropicProvider(api_key="unused", model="claude-opus-5", client=client)

    with pytest.raises(ProviderError):
        provider.respond(LLMQuery(text="hello"))
