"""Tests for `ConversationMemory`: bounded, deletable LLM conversation history.

No provider or network is involved here -- this class only ever produces
plain query text; `LLMProvider.respond()` itself stays untouched (a single
`LLMQuery` in, a single `LLMReply` out).
"""

from __future__ import annotations

import pytest

from visionai.intelligence.memory import ConversationMemory, ConversationTurn


def test_conversation_memory_rejects_invalid_bounds() -> None:
    with pytest.raises(ValueError, match="max_turns"):
        ConversationMemory(max_turns=0)
    with pytest.raises(ValueError, match="max_context_chars"):
        ConversationMemory(max_context_chars=0)


def test_conversation_memory_starts_empty_and_returns_the_bare_question() -> None:
    memory = ConversationMemory()

    assert memory.turns == ()
    assert memory.build_query_text("what time is it?") == "what time is it?"


def test_conversation_memory_records_and_exposes_turns_oldest_first() -> None:
    memory = ConversationMemory()

    memory.record("first question", "first answer")
    memory.record("second question", "second answer")

    assert memory.turns == (
        ConversationTurn(query="first question", reply="first answer"),
        ConversationTurn(query="second question", reply="second answer"),
    )


def test_conversation_memory_evicts_the_oldest_turn_past_max_turns() -> None:
    memory = ConversationMemory(max_turns=2)

    memory.record("q1", "a1")
    memory.record("q2", "a2")
    memory.record("q3", "a3")

    assert [turn.query for turn in memory.turns] == ["q2", "q3"]


def test_conversation_memory_clear_deletes_all_history() -> None:
    memory = ConversationMemory()
    memory.record("q1", "a1")

    memory.clear()

    assert memory.turns == ()
    assert memory.build_query_text("q2") == "q2"


def test_conversation_memory_build_query_text_prefixes_recorded_turns() -> None:
    memory = ConversationMemory()
    memory.record("what is 2+2?", "4")

    built = memory.build_query_text("and 3+3?")

    assert built == "User: what is 2+2?\nAssistant: 4\nUser: and 3+3?"


def test_conversation_memory_build_query_text_keeps_most_recent_turns_first() -> None:
    memory = ConversationMemory(max_turns=10)
    memory.record("q1", "a1")
    memory.record("q2", "a2")

    built = memory.build_query_text("q3")

    assert built == "User: q1\nAssistant: a1\nUser: q2\nAssistant: a2\nUser: q3"


def test_conversation_memory_drops_oldest_turns_first_when_over_the_char_budget() -> None:
    # Each turn's rendered entry is well over 20 chars, so a tight budget can
    # only fit the most recent one.
    memory = ConversationMemory(max_turns=10, max_context_chars=60)
    memory.record("an older question", "an older reply")
    memory.record("a newer question", "a newer reply")

    built = memory.build_query_text("q3")

    assert "an older question" not in built
    assert "a newer question" in built
    assert built.endswith("User: q3")


def test_conversation_memory_never_drops_or_truncates_the_new_question() -> None:
    memory = ConversationMemory(max_turns=10, max_context_chars=10)
    memory.record("q1", "a1")

    built = memory.build_query_text("a question longer than the whole budget")

    assert built == "a question longer than the whole budget"


def test_conversation_memory_returns_the_bare_question_when_no_turn_fits_the_budget() -> None:
    # The trailer itself fits, but the one recorded turn is too long to include
    # alongside it -- rather than truncate the turn, drop it entirely.
    memory = ConversationMemory(max_turns=10, max_context_chars=20)
    memory.record("a much longer question than the budget allows", "a much longer reply too")

    assert memory.build_query_text("hi") == "hi"


def test_conversation_memory_build_query_text_never_exceeds_the_char_budget() -> None:
    memory = ConversationMemory(max_turns=50, max_context_chars=200)
    for i in range(50):
        memory.record(f"question number {i}", f"reply number {i}")

    built = memory.build_query_text("final question")

    assert len(built) <= 200
    assert built.endswith("User: final question")
