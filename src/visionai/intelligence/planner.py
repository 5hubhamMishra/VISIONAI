"""Maps free text onto one of `TextCommandPlanner`'s reviewed phrases via an LLM.

Propose only -- this module never builds an `ActionRequest` or touches the
dispatcher itself. Its only job is turning loose natural language into
either one exact, already-reviewed command phrase or nothing; the caller is
responsible for running that phrase through the real `TextCommandPlanner`
(the same one `--text` uses) to see what it would actually do.

The LLM's raw reply is never trusted just because it claims to have
followed instructions: `suggest_command()` independently re-validates it
against the same reviewed vocabulary before returning anything. A
hallucinated phrase outside that vocabulary -- including a prompt-injection
attempt -- always returns `None` here, the same as an explicit "no match."
"""

from __future__ import annotations

from dataclasses import dataclass

from visionai.core.events import contains_unsafe_characters
from visionai.intelligence.provider import LLMProvider, LLMQuery
from visionai.orchestration.text_planner import reviewed_phrases

_SEARCH_TEMPLATE = "search for <your query>"
_SEARCH_PREFIX = "search for "
_CLARIFY_PREFIX = "CLARIFY:"


@dataclass(frozen=True, slots=True)
class CommandSuggestion:
    phrase: str | None = None
    clarification: str | None = None


def suggest_command_result(provider: LLMProvider, utterance: str) -> CommandSuggestion:
    """Return one reviewed phrase, or one human-facing clarification question."""

    phrases = reviewed_phrases()
    query = LLMQuery(text=_build_prompt(phrases, utterance))
    reply = provider.respond(query).text.strip()
    if reply.upper().startswith(_CLARIFY_PREFIX):
        question = reply[len(_CLARIFY_PREFIX) :].strip()
        if question and not contains_unsafe_characters(question, allow_line_breaks=False):
            return CommandSuggestion(clarification=question)
        return CommandSuggestion()
    return CommandSuggestion(phrase=_validate_reply(reply, phrases))


def suggest_command(provider: LLMProvider, utterance: str) -> str | None:
    """Ask the LLM to map `utterance` onto one reviewed phrase, or nothing."""

    return suggest_command_result(provider, utterance).phrase


def _build_prompt(phrases: tuple[str, ...], utterance: str) -> str:
    menu = "\n".join(f"- {phrase}" for phrase in phrases)
    return (
        "You translate a user's request into one of a fixed set of exact command "
        "phrases, or decide none apply. Known phrases:\n"
        f"{menu}\n\n"
        "Reply with exactly one of the phrases above, verbatim, if the request "
        "clearly matches one -- for the search phrase, replace <your query> with "
        "the actual thing to search for. If the request is ambiguous, reply with "
        "exactly CLARIFY: followed by one concise question for the human. Otherwise "
        "reply with exactly the word NONE. Do not explain, do not add punctuation, "
        "do not invent a phrase not in the list.\n\n"
        f"Request: {utterance}"
    )


def _validate_reply(reply: str, phrases: tuple[str, ...]) -> str | None:
    # A command phrase must be a single line, unlike `SafeText` (which
    # exempts tab/newline/CR for multi-turn conversation context).
    if contains_unsafe_characters(reply, allow_line_breaks=False):
        return None
    if reply.upper() == "NONE":
        return None
    lowered = reply.lower()
    if lowered == _SEARCH_TEMPLATE:
        return None
    if lowered in {phrase.lower() for phrase in phrases if phrase != _SEARCH_TEMPLATE}:
        return reply
    if lowered.startswith(_SEARCH_PREFIX) and len(lowered) > len(_SEARCH_PREFIX):
        return reply
    return None
