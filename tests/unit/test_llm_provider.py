"""Tests for the LLM provider boundary: typed contracts and the safe fallback."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from visionai.intelligence import DeterministicFallbackProvider, LLMQuery, LLMReply


def test_llm_query_rejects_control_characters() -> None:
    with pytest.raises(ValidationError):
        LLMQuery(text="open notepad\x00")


def test_llm_query_rejects_oversized_text() -> None:
    with pytest.raises(ValidationError):
        LLMQuery(text="a" * 2001)


def test_llm_query_accepts_ordinary_text() -> None:
    query = LLMQuery(text="what is 2+2?")

    assert query.text == "what is 2+2?"


def test_llm_reply_rejects_control_characters() -> None:
    with pytest.raises(ValidationError):
        LLMReply(text="answer\x07")


def test_deterministic_fallback_provider_returns_fixed_message_with_no_io() -> None:
    provider = DeterministicFallbackProvider()

    reply = provider.respond(LLMQuery(text="anything"))

    assert "No LLM provider is configured" in reply.text
    assert "VISIONAI_LLM_PROVIDER" in reply.text


@pytest.mark.parametrize("contract", [LLMQuery, LLMReply])
def test_llm_contract_rejects_unknown_tool_fields(
    contract: type[LLMQuery] | type[LLMReply],
) -> None:
    with pytest.raises(ValidationError):
        contract.model_validate({"text": "open notepad", "tool": "shell"})
