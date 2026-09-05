"""Bounded, deletable conversation history for LLM providers.

Conversation memory is opt-in and lives entirely on the caller's side of
the `LLMProvider` boundary -- providers still only ever see one `LLMQuery`
per call (`respond(query) -> reply`), matching every other adapter
boundary's synchronous, stateless shape (`docs/DECISIONS/0004-llm-provider-
choice.md` deliberately deferred conversation memory rather than widen
that Protocol). `ConversationMemory` instead builds the *next* query's
text by prefixing as much recent history as fits, and bounds what it
retains two ways: a maximum number of turns (oldest evicted first) and a
maximum character budget, so a long-running conversation can never grow an
outgoing query past `LLMQuery`'s own validated length limit. `clear()` is
the explicit deletion path this history needs, matching the master
prompt's Section 12 "retention limits and deletion" requirement. Nothing
here is persisted to disk -- history lives only in process memory for as
long as the caller keeps the object, the same transient posture this
project already takes with raw audio/camera frames.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

_DEFAULT_MAX_TURNS = 8
_DEFAULT_MAX_CONTEXT_CHARS = 1200


@dataclass(frozen=True, slots=True)
class ConversationTurn:
    """One remembered question/answer pair."""

    query: str
    reply: str


class ConversationMemory:
    """A small, bounded, explicitly clearable question/answer history."""

    def __init__(
        self,
        *,
        max_turns: int = _DEFAULT_MAX_TURNS,
        max_context_chars: int = _DEFAULT_MAX_CONTEXT_CHARS,
    ) -> None:
        if max_turns < 1:
            raise ValueError("max_turns must be at least 1")
        if max_context_chars < 1:
            raise ValueError("max_context_chars must be at least 1")
        self._max_context_chars = max_context_chars
        self._turns: deque[ConversationTurn] = deque(maxlen=max_turns)

    @property
    def turns(self) -> tuple[ConversationTurn, ...]:
        """A snapshot of retained turns, oldest first. Callers cannot mutate history through it."""

        return tuple(self._turns)

    def record(self, query: str, reply: str) -> None:
        """Remember one turn. The oldest turn is dropped once `max_turns` is exceeded."""

        self._turns.append(ConversationTurn(query=query, reply=reply))

    def clear(self) -> None:
        """Delete all retained history."""

        self._turns.clear()

    def build_query_text(self, question: str) -> str:
        """Prefix as much recent history as fits `max_context_chars`, most-recent-first.

        The new `question` is never dropped or truncated to make room -- if
        it alone already reaches the character budget (or no history has
        been recorded yet), it is returned unchanged, so a lone question's
        validation behavior against `LLMQuery`'s length limit is identical
        to calling this with no memory at all. Only prior turns are ever
        traded away to keep the combined text within budget.
        """

        trailer = f"User: {question}"
        if not self._turns or len(trailer) >= self._max_context_chars:
            return question

        budget = self._max_context_chars - len(trailer)
        included: list[str] = []
        for turn in reversed(self._turns):
            entry = f"User: {turn.query}\nAssistant: {turn.reply}\n"
            if len(entry) > budget:
                break
            included.append(entry)
            budget -= len(entry)

        if not included:
            return question

        included.reverse()
        return "".join(included) + trailer
